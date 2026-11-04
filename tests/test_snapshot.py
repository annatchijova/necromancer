"""Snapshot scope: HEAD investigations read committed blobs only;
worktree investigations say so and report divergence."""

import hashlib
import os
import subprocess
from pathlib import Path

from necromancer.cli import investigate
from necromancer.excavator import excavate
from necromancer.models import ClaimState


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ)
    env["GIT_AUTHOR_DATE"] = "2024-03-01T10:00:00+00:00"
    env["GIT_COMMITTER_DATE"] = "2024-03-01T10:00:00+00:00"
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, env=env, capture_output=True, text=True,
    ).stdout.strip()


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "snap"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "validator.py").write_text(
        "def validate(v):\n    return v.replace('<script>', '')\n", encoding="utf-8")
    (repo / "README.md").write_text(
        "# P\n\nSecurity: the XSS vulnerability was fixed.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "fix: fix XSS validation")
    return repo


def test_head_snapshot_ignores_uncommitted_edits(tmp_path):
    repo = _repo(tmp_path)
    committed = (repo / "validator.py").read_text(encoding="utf-8")
    (repo / "validator.py").write_text(
        "def validate(v):\n    # TODO: incomplete\n    return v\n", encoding="utf-8")

    head = excavate(str(repo), snapshot="head")
    assert head.snapshot == "head"
    assert head.texts["validator.py"] == committed
    artifact = next(a for a in head.artifacts if a.path == "validator.py")
    assert artifact.sha256 == hashlib.sha256(committed.encode()).hexdigest()
    assert head.divergent_files == []

    report = investigate(str(repo))
    claim = next(c for c in report.claims if c.verb == "FIXED" and c.source_kind == "DOC")
    assert report.snapshot == "head"
    assert claim.state == ClaimState.SUPPORTED  # committed patch has no TODO


def test_worktree_snapshot_reports_divergence(tmp_path):
    repo = _repo(tmp_path)
    (repo / "validator.py").write_text(
        "def validate(v):\n    # TODO: incomplete\n    return v\n", encoding="utf-8")

    worktree = excavate(str(repo), snapshot="worktree")
    assert worktree.snapshot == "worktree"
    assert worktree.divergent_files == ["validator.py"]
    assert any("snapshot=worktree" in warning for warning in worktree.warnings)
    assert "TODO" in worktree.texts["validator.py"]

    report = investigate(str(repo), snapshot="worktree")
    claim = next(c for c in report.claims if c.verb == "FIXED" and c.source_kind == "DOC")
    assert report.snapshot == "worktree"
    assert claim.state == ClaimState.CONTRADICTED  # uncommitted TODO now in scope
