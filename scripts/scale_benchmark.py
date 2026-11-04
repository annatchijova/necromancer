#!/usr/bin/env python3
"""Synthetic scale harness: build a generated repository, excavate it, report.

Measures wall time, peak RSS of this process, commits, claims, contradictions
and skipped material. The repository is generated deterministically so the run
is reproducible; it is NOT a measurement of any real project.
"""

from __future__ import annotations

import os
import resource
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from necromancer.excavator import excavate  # noqa: E402
from necromancer.cli import investigate  # noqa: E402
from necromancer.coroner import analyze  # noqa: E402


def git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=repo, check=True,
        env={**os.environ, "GIT_AUTHOR_NAME": "Scale", "GIT_AUTHOR_EMAIL": "s@x",
             "GIT_COMMITTER_NAME": "Scale", "GIT_COMMITTER_EMAIL": "s@x"},
        capture_output=True, text=True)


def build(repo: Path, commits: int = 300, files: int = 200) -> None:
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    for i in range(files):
        (repo / f"module_{i % 25}").mkdir(exist_ok=True)
        (repo / f"module_{i % 25}" / f"file_{i}.py").write_text(
            f"VALUE_{i} = {i}\n", encoding="utf-8")
    (repo / "README.md").write_text("# GENERATED-SCALE-FIXTURE\n\nFIXED generated bug\n",
                                    encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "fix: generated fix")
    for i in range(commits - 1):
        (repo / "log.txt").write_text(f"line {i}\n", encoding="utf-8")
        git(repo, "add", "-A")
        git(repo, "commit", "-m", f"chore: generated commit {i}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="necromancer-scale-") as tmp:
        repo = Path(tmp) / "generated"
        commits = int(sys.argv[1]) if len(sys.argv) > 1 else 300
        files = int(sys.argv[2]) if len(sys.argv) > 2 else 200
        build(repo, commits, files)
        started = time.perf_counter()
        excavation = excavate(str(repo))
        report = investigate(str(repo))
        seconds = time.perf_counter() - started
    rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    print(f"commits={len(excavation.commits)} file_change_entries={sum(len(c.files) for c in excavation.commits)}")
    print(f"claims={len(report.claims)} contradictions={len(report.contradictions)}")
    print(f"wall_seconds={seconds:.2f} peak_rss_mb={rss_kb / 1024:.1f}")
    print(f"warnings={len(excavation.warnings)} skipped_texts~{excavation.stats.get('skipped_texts', 0)}")
    print(f"stats={excavation.stats}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
