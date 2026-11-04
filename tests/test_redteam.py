"""Red team round 3: adversarial probes against NECROMANCER itself.

Threat model: the attacker controls the target repository (files, names,
attributes, local git config), the model endpoint responses, and input
sizes. The attacker cannot modify NECROMANCER code.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

from necromancer import llm
from necromancer.cli import investigate
from necromancer.excavator import excavate


def _git(repo: Path, *args: str) -> None:
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2024-05-01T10:00:00+00:00"
    env["GIT_COMMITTER_DATE"] = "2024-05-01T10:00:00+00:00"
    subprocess.run(["git", "-C", str(repo), *args],
                   check=True, env=env, capture_output=True)


def _repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    return repo


def test_git_filter_driver_is_never_executed(tmp_path):
    canary = tmp_path / "canary.txt"
    repo = _repo(tmp_path, "filter")
    (repo / ".gitattributes").write_text("*.py filter=evil\n", encoding="utf-8")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    _git(repo, "config", "filter.evil.clean", f"touch {canary}")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat")
    if canary.exists():
        canary.unlink()  # the setup commit itself may run the clean filter
    excavate(str(repo), snapshot="head")
    excavate(str(repo), snapshot="worktree")
    assert not canary.exists(), "excavation executed a repository filter driver"


def test_newline_in_filename_keeps_exact_path(tmp_path):
    repo = _repo(tmp_path, "oddname")
    odd = repo / "odd\nname.py"
    odd.write_text("x = 1\n", encoding="utf-8")
    (repo / "README.md").write_text("# P\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat")
    result = excavate(str(repo), snapshot="head")
    assert "odd\nname.py" in [artifact.path for artifact in result.artifacts]


def test_large_blob_is_hashed_but_not_text_indexed(tmp_path):
    repo = _repo(tmp_path, "big")
    content = ("# filler line\n" * 200_000).encode()
    (repo / "big.py").write_bytes(content)
    (repo / "README.md").write_text("# P\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat")
    result = excavate(str(repo), snapshot="head")
    artifact = next(a for a in result.artifacts if a.path == "big.py")
    assert artifact.sha256 == hashlib.sha256(content).hexdigest()
    assert "big.py" not in result.texts


def test_model_output_is_capped(synthetic):
    def fake_transport(url, payload, headers):
        many = [
            {"group": "g", "statement": f"hypothesis {i}", "discriminators": ["x"]}
            for i in range(500)
        ]
        return {"choices": [{"message": {"content": json.dumps({"hypotheses": many})}}]}

    provider = llm.OpenAICompatibleProvider(
        base_url="http://localhost:9999/v1", model="m", transport=fake_transport)
    report = investigate(str(synthetic["a"]))
    assert len(provider.generate(report)) <= 50


def test_worktree_symlink_is_never_followed_outside_repo(tmp_path):
    outside = tmp_path / "outside-secret.txt"
    outside.write_text("SECRET-OUTSIDE-REPO", encoding="utf-8")
    repo = _repo(tmp_path, "link")
    (repo / "README.md").write_text("# P\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat")
    (repo / "linked.py").symlink_to(outside)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "add link")
    result = excavate(str(repo), snapshot="worktree")
    assert "SECRET-OUTSIDE-REPO" not in "\n".join(result.texts.values())


def test_seal_is_stable_across_hash_seeds(synthetic):
    code = (
        "import sys; sys.path.insert(0, 'src');"
        "from necromancer.cli import investigate;"
        f"print(investigate(r'{synthetic['a']}').seal)"
    )
    seals = set()
    root = Path(__file__).resolve().parents[1]
    for seed in ("1", "42"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=root, env=env, capture_output=True, text=True, check=True)
        seals.add(proc.stdout.strip())
    assert len(seals) == 1
