"""Round 3 adversarial histories: cherry-picks, reverts, renames, squash
merges, shallow clones and documentation copied from unrelated projects.
Where semantics cannot bind, the honest answer is UNVERIFIED.
"""

import os
import subprocess
from pathlib import Path

from necromancer.cli import investigate
from necromancer.excavator import excavate
from necromancer.models import ClaimState


def _git(repo: Path, *args: str, day: int = 1) -> str:
    env = dict(os.environ)
    stamp = f"2024-06-{day:02d}T10:00:00+00:00"
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, env=env, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path, name: str) -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    return repo


def _commit(repo: Path, files: dict[str, str], message: str, day: int) -> str:
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A", day=day)
    _git(repo, "commit", "-m", message, day=day)
    return _git(repo, "rev-parse", "HEAD", day=day)


def _doc_fixed_claim(report, needle: str):
    return next(
        c for c in report.claims
        if needle in c.text.lower() and c.source_kind == "DOC" and c.verb == "FIXED")


def test_cherry_picked_fix_binds_to_the_cherry_pick(tmp_path):
    repo = _repo(tmp_path, "cherry")
    _commit(repo, {"parser.py": "def p(t):\n    return t.splitlines()[:-1]\n",
                   "README.md": "# P\n"}, "feat: parser", 1)
    _git(repo, "checkout", "-b", "work", day=2)
    _commit(repo, {"parser.py": "def p(t):\n    return t.splitlines()\n",
                   "tests/test_parser.py": "def test_p():\n    assert True  # parser\n"},
            "fix: fixed parser last line", 3)
    _git(repo, "checkout", "main", day=4)
    work_tip = _git(repo, "rev-parse", "work", day=4)
    subprocess.run(["git", "-C", str(repo), "cherry-pick", work_tip],
                   check=True, capture_output=True,
                   env=dict(os.environ, GIT_AUTHOR_DATE="2024-06-05T10:00:00+00:00",
                            GIT_COMMITTER_DATE="2024-06-05T10:00:00+00:00"))
    picked = _git(repo, "rev-parse", "HEAD", day=5)
    _commit(repo, {"README.md": "# P\n\nThe parser last line was fixed.\n"},
            "docs: status", 6)
    report = investigate(str(repo))
    claim = _doc_fixed_claim(report, "parser")
    assert claim.state == ClaimState.SUPPORTED
    assert picked[:12] in [link.evidence_ref for link in report.links
                           if link.claim_id == claim.claim_id]


def test_reverted_fix_is_contradicted_again(tmp_path):
    repo = _repo(tmp_path, "revert")
    _commit(repo, {"validator.py": "def v(x):\n    return x\n",
                   "README.md": "# P\n"}, "feat: base", 1)
    _commit(repo, {"validator.py": "def v(x):\n    return x.replace('<script>', '')\n"},
            "fix: fix XSS validation", 2)
    _commit(repo, {"validator.py": "def v(x):\n    return x\n"},
            "Revert \"fix: fix XSS validation\"", 3)
    _commit(repo, {"README.md": "# P\n\nThe XSS issue was fixed.\n"}, "docs: status", 4)
    report = investigate(str(repo))
    claim = _doc_fixed_claim(report, "xss")
    assert claim.state == ClaimState.CONTRADICTED
    assert any(item.kind == "REVERTED_FIX" for item in report.contradictions)


def test_renamed_file_fix_still_binds(tmp_path):
    repo = _repo(tmp_path, "rename")
    _commit(repo, {"validator.py": "def v(x):\n    return x\n",
                   "README.md": "# P\n"}, "feat: base", 1)
    (repo / "validator.py").rename(repo / "sanitizer.py")
    (repo / "sanitizer.py").write_text(
        "def v(x):\n    # TODO: incomplete\n    return x\n", encoding="utf-8")
    _git(repo, "add", "-A", day=2)
    _git(repo, "commit", "-m", "fix: fix XSS validation", day=2)
    _commit(repo, {"README.md": "# P\n\nThe XSS issue was fixed.\n"}, "docs: status", 3)
    report = investigate(str(repo))
    claim = _doc_fixed_claim(report, "xss")
    assert claim.state == ClaimState.CONTRADICTED
    assert any(item.kind == "INCOMPLETE_PATCH" for item in report.contradictions)


def test_squash_merge_message_binds(tmp_path):
    repo = _repo(tmp_path, "squash")
    _commit(repo, {"parser.py": "def p(t):\n    return t.splitlines()[:-1]\n",
                   "README.md": "# P\n"}, "feat: parser", 1)
    _commit(repo, {
        "parser.py": "def p(t):\n    return t.splitlines()\n",
        "tests/test_parser.py": "def test_p():\n    assert True  # parser\n",
        "README.md": "# P\n\nThe parser last line was fixed.\n",
    }, "feat: parser rework\n\nfix: fixed parser last line", 2)
    report = investigate(str(repo))
    claim = _doc_fixed_claim(report, "parser")
    assert claim.state == ClaimState.SUPPORTED


def test_shallow_clone_is_reported_as_incomplete_history(tmp_path, synthetic):
    dest = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{synthetic['a']}", str(dest)],
        check=True, capture_output=True)
    result = excavate(str(dest), snapshot="head")
    assert any("shallow" in warning for warning in result.warnings)


def test_copied_documentation_stays_unverified(tmp_path):
    repo = _repo(tmp_path, "copied")
    _commit(repo, {
        "calculator.py": "def add(a, b):\n    return a + b\n",
        "README.md": "# Other Project\n\nThe PDF export feature was implemented.\n",
    }, "feat: calculator with copied readme", 1)
    report = investigate(str(repo))
    claim = next(c for c in report.claims if "pdf" in c.text.lower())
    assert claim.state == ClaimState.UNVERIFIED
