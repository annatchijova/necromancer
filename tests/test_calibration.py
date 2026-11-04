"""Calibration controls for the incomplete-patch detector.

Baseline failure (raven-memory, Round 3): substring matching on lowered
text fired on the Spanish word "todo" inside data and on "xxx" inside
identifiers, producing contradictions with zero strict markers.
These controls must keep the detector able to fail in both directions.
"""

import os
import subprocess
from pathlib import Path

from necromancer.cli import investigate
from necromancer.models import ClaimState


def _git(repo: Path, *args: str, day: int = 1) -> str:
    env = dict(os.environ)
    stamp = f"2024-07-{day:02d}T10:00:00+00:00"
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, env=env, capture_output=True, text=True).stdout.strip()


def _repo(tmp_path: Path, validator: str) -> Path:
    repo = tmp_path / "cal"
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "validator.py").write_text("def v(x):\n    return x\n", encoding="utf-8")
    (repo / "README.md").write_text("# P\n", encoding="utf-8")
    _git(repo, "add", "-A", day=1)
    _git(repo, "commit", "-m", "feat: base", day=1)
    (repo / "validator.py").write_text(validator, encoding="utf-8")
    _git(repo, "add", "-A", day=2)
    _git(repo, "commit", "-m", "fix: fix XSS validation", day=2)
    (repo / "README.md").write_text(
        "# P\n\nSecurity: the XSS vulnerability was fixed.\n", encoding="utf-8")
    _git(repo, "add", "-A", day=3)
    _git(repo, "commit", "-m", "docs: status", day=3)
    return repo


def _claim(report):
    return next(c for c in report.claims
                if c.verb == "FIXED" and c.source_kind == "DOC")


def test_spanish_todo_word_is_not_an_incomplete_marker(tmp_path):
    repo = _repo(tmp_path, (
        "def v(x):\n"
        "    # todo el sistema valida la entrada antes de seguir\n"
        "    return x.replace('<script>', '')\n"))
    report = investigate(str(repo))
    assert _claim(report).state == ClaimState.SUPPORTED
    assert report.health["todo_fixme_references"] == 0


def test_xxx_inside_identifier_is_not_a_marker(tmp_path):
    repo = _repo(tmp_path, (
        "def v(x):\n"
        "    axxxb = x.replace('<script>', '')\n"
        "    return axxxb\n"))
    report = investigate(str(repo))
    assert _claim(report).state == ClaimState.SUPPORTED


def test_real_todo_marker_still_contradicts(tmp_path):
    repo = _repo(tmp_path, (
        "def v(x):\n"
        "    # TODO: only strips script tags\n"
        "    return x.replace('<script>', '')\n"))
    report = investigate(str(repo))
    assert _claim(report).state == ClaimState.CONTRADICTED
    assert any(item.kind == "INCOMPLETE_PATCH" for item in report.contradictions)
