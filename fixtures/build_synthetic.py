"""Build the three synthetic repositories with known histories.

Each history hides one contradiction that NECROMANCER must find:
A. README claims a security fix; the patch is incomplete and untested.
B. The missing solution lives on an unmerged branch.
C. Documentation claims a completed feature that is only a stub.

Usage: python fixtures/build_synthetic.py /tmp/necromancer-fixtures
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _git(repo: Path, *args: str, day: int = 1) -> None:
    env = dict(os.environ)
    stamp = f"2024-01-{day:02d}T10:00:00+00:00"
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, env=env, capture_output=True, text=True,
    )


def _write(repo: Path, rel: str, content: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def _commit_all(repo: Path, message: str, day: int) -> None:
    _git(repo, "add", "-A", day=day)
    _git(repo, "commit", "-m", message, day=day)


def _init(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "Fixture Builder")


def build_a(base: Path) -> Path:
    repo = base / "fixture-a-incomplete-fix"
    _init(repo)
    _write(repo, "validator.py", "def validate_input(value):\n    return value\n")
    _write(repo, "README.md", "# Fixture A\n\nA small validator project.\n")
    _commit_all(repo, "feat: add input validator", day=1)
    _write(repo, "validator.py",
           "def validate_input(value):\n"
           "    # TODO: incomplete, only strips script tags\n"
           "    return value.replace('<script>', '')\n")
    _write(repo, "README.md",
           "# Fixture A\n\nSecurity: the XSS vulnerability was fixed on 2024-06-14.\n")
    _commit_all(repo, "fix: fix XSS validation", day=2)
    return repo


def build_b(base: Path) -> Path:
    repo = base / "fixture-b-abandoned-branch"
    _init(repo)
    _write(repo, "parser.py",
           "def parse_lines(text):\n"
           "    lines = text.splitlines()\n"
           "    return lines[:-1]\n")
    _write(repo, "tests/test_parser.py",
           "from parser import parse_lines\n\n"
           "def test_parse_lines_keeps_every_line():\n"
           "    assert parse_lines('a\\nb') == ['a', 'b']\n")
    _write(repo, "README.md",
           "# Fixture B\n\nKnown issue: the parser drops the last line. "
           "The bug is still open.\n")
    _commit_all(repo, "feat: add line parser", day=1)
    _git(repo, "checkout", "-b", "fix/parser-last-line", day=2)
    _write(repo, "parser.py",
           "def parse_lines(text):\n"
           "    return text.splitlines()\n")
    _write(repo, "tests/test_parser.py",
           "from parser import parse_lines\n\n"
           "def test_parse_lines_keeps_every_line():\n"
           "    assert parse_lines('a\\nb') == ['a', 'b']\n\n"
           "def test_parse_lines_single_line():\n"
           "    assert parse_lines('only') == ['only']\n")
    _commit_all(repo, "fix: fixed parser dropping the last line", day=3)
    _git(repo, "checkout", "main", day=4)
    return repo


def build_c(base: Path) -> Path:
    repo = base / "fixture-c-false-completion"
    _init(repo)
    _write(repo, "exporter.py",
           "# pdf export support\n"
           "def export_pdf(document):\n"
           "    raise NotImplementedError('pdf export pending')\n")
    _write(repo, "README.md",
           "# Fixture C\n\nStatus: the PDF export feature was implemented and verified.\n")
    _write(repo, "CHANGELOG.md", "# Changelog\n\nv1.0: PDF export completed.\n")
    _write(repo, "docs/guide.md",
           "# Guide\n\nNote: PDF export is not implemented yet.\n")
    _commit_all(repo, "docs: announce v1.0", day=1)
    return repo


BUILDERS = {"a": build_a, "b": build_b, "c": build_c}


def build_all(base: Path) -> dict[str, Path]:
    return {key: builder(base) for key, builder in BUILDERS.items()}


if __name__ == "__main__":
    destination = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/necromancer-fixtures")
    for key, path in build_all(destination).items():
        print(f"fixture {key}: {path}")
