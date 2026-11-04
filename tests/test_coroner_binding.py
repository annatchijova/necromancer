"""FIXED claims must bind to their own fix commit, never to the newest
fix in the repository (batch laundering). Each test is an independent bug.
"""

import os
import subprocess
from pathlib import Path

from necromancer.cli import investigate
from necromancer.models import ClaimState


def _git(repo: Path, *args: str, day: int = 1) -> str:
    env = dict(os.environ)
    stamp = f"2024-02-{day:02d}T10:00:00+00:00"
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, env=env, capture_output=True, text=True,
    )
    return proc.stdout.strip()


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


def test_unrelated_fix_does_not_support_claim(tmp_path):
    repo = _repo(tmp_path, "unrelated")
    _commit(repo, {"auth.py": "def login():\n    return False\n"}, "feat: auth", 1)
    _commit(repo, {"auth.py": "def login():\n    return True\n"},
            "fix: fixed login redirect", 2)
    _commit(repo, {"README.md": "# P\n\nThe database timeout was fixed.\n"},
            "docs: status", 3)
    report = investigate(str(repo))
    claim = next(c for c in report.claims if "database" in c.text.lower())
    assert claim.state == ClaimState.UNVERIFIED
    assert not any(
        link.claim_id == claim.claim_id and link.relation.value == "SUPPORTS"
        for link in report.links
    )


def test_two_independent_bugs_bind_to_their_own_commits(tmp_path):
    repo = _repo(tmp_path, "twobugs")
    _commit(repo, {
        "validator.py": "def validate(v):\n    return v\n",
        "auth.py": "def login():\n    return False\n",
        "README.md": "# P\n",
    }, "feat: base", 1)
    xss_fix = _commit(repo, {
        "validator.py": "def validate(v):\n    # TODO: incomplete\n    return v.replace('<script>', '')\n",
    }, "fix: fix XSS validation", 2)
    login_fix = _commit(repo, {
        "auth.py": "def login():\n    return True\n",
        "tests/test_auth.py": "def test_login():\n    assert True  # login\n",
    }, "fix: fixed login redirect", 3)
    _commit(repo, {
        "README.md": "# P\n\nThe XSS issue was fixed. The login redirect was fixed.\n",
    }, "docs: status", 4)

    report = investigate(str(repo))
    xss = next(c for c in report.claims if "xss" in c.text.lower() and c.source_kind == "DOC")
    login = next(c for c in report.claims if "login" in c.text.lower() and c.source_kind == "DOC")
    assert xss.state == ClaimState.CONTRADICTED
    assert login.state == ClaimState.SUPPORTED
    xss_links = [link.evidence_ref for link in report.links if link.claim_id == xss.claim_id]
    login_links = [link.evidence_ref for link in report.links if link.claim_id == login.claim_id]
    assert xss_fix[:12] in xss_links
    assert login_fix[:12] in login_links


def test_commit_claim_binds_to_its_own_commit_not_the_newest_fix(tmp_path):
    repo = _repo(tmp_path, "selfbind")
    old_fix = _commit(repo, {
        "validator.py": "def validate(v):\n    # TODO: incomplete\n    return v\n",
        "README.md": "# P\n",
    }, "fix: fix XSS validation", 1)
    _commit(repo, {"auth.py": "def login():\n    return True\n"},
            "fix: fixed login redirect", 2)
    report = investigate(str(repo))
    own = next(
        c for c in report.claims
        if c.source_kind == "COMMIT" and c.origin == f"commit:{old_fix}"
    )
    assert own.state == ClaimState.CONTRADICTED
