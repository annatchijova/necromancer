"""Read-only Git excavation. The target repository is untrusted data.

Only allowlisted, read-only Git subcommands run, with optional locks
disabled. Repository code is never executed and the target is never
written to.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .models import Artifact, BranchInfo, CommitRecord

ALLOWED_SUBCOMMANDS = frozenset(
    {"log", "show", "branch", "tag", "rev-parse", "ls-tree", "merge-base", "rev-list"}
)
MAX_COMMITS = 5000
MAX_TEXT_BYTES = 200_000
DOC_SUFFIXES = {".md", ".rst", ".txt"}
CODE_SUFFIXES = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".rb",
    ".php", ".c", ".h", ".cpp", ".cs", ".sh", ".sql",
}


class ExcavationError(RuntimeError):
    pass


@dataclass
class Excavation:
    repo_path: str
    head: str
    current_branch: str
    commits: list[CommitRecord] = field(default_factory=list)
    branches: list[BranchInfo] = field(default_factory=list)
    tags: list[tuple[str, str]] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _git(repo: Path, args: list[str]) -> str:
    if not args or args[0] not in ALLOWED_SUBCOMMANDS:
        raise ExcavationError(f"git subcommand not allowlisted: {args[:1]}")
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, timeout=60, env=env, check=False,
    )
    if proc.returncode != 0:
        raise ExcavationError(f"git {' '.join(args[:2])} failed: {proc.stderr.strip()[:300]}")
    return proc.stdout


def resolve_repo(raw: str) -> Path:
    repo = Path(raw).expanduser().resolve()
    if not repo.is_dir():
        raise ExcavationError(f"not a directory: {raw}")
    if not (repo / ".git").exists():
        raise ExcavationError(f"not a git repository: {raw}")
    return repo


def _kind_for(path: str) -> str:
    lower = path.lower()
    suffix = Path(lower).suffix
    name = Path(lower).name
    if "test" in Path(lower).parts or name.startswith("test_") or "_test." in name:
        return "TEST"
    if suffix in DOC_SUFFIXES or name.startswith(("readme", "changelog", "history", "news")):
        return "DOC"
    if suffix in CODE_SUFFIXES:
        return "CODE"
    return "OTHER"


def excavate(raw_path: str) -> Excavation:
    repo = resolve_repo(raw_path)
    result = Excavation(repo_path=str(repo), head="", current_branch="")
    result.head = _git(repo, ["rev-parse", "HEAD"]).strip()
    result.current_branch = _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()

    fmt = "%H%x1f%P%x1f%an%x1f%aI%x1f%s%x1f%b%x1e"
    raw_log = _git(repo, ["log", "--all", f"--max-count={MAX_COMMITS}", f"--format={fmt}"])
    records = [chunk for chunk in raw_log.split("\x1e") if chunk.strip()]
    if len(records) >= MAX_COMMITS:
        result.warnings.append(f"commit history truncated at {MAX_COMMITS} commits")
    for chunk in records:
        parts = chunk.strip("\n").split("\x1f")
        if len(parts) < 6:
            continue
        commit_hash, parents, author, date_iso, subject, body = parts[:6]
        files: list[tuple[str, str]] = []
        shown = _git(repo, ["show", "--name-status", "--format=", commit_hash])
        for line in shown.splitlines():
            if "\t" not in line:
                continue
            status, path = line.split("\t", 1)
            files.append((status.strip(), path.strip()))
        result.commits.append(CommitRecord(
            commit_hash=commit_hash.strip(),
            parents=tuple(parents.split()) if parents.strip() else (),
            author=author, date_iso=date_iso, subject=subject,
            body=body.strip(), files=tuple(files),
        ))

    merged_names: set[str] = set()
    merged_raw = _git(repo, ["branch", "--merged", "HEAD", "--format=%(refname:short)"])
    merged_names = {line.strip() for line in merged_raw.splitlines() if line.strip()}
    branch_raw = _git(repo, ["branch", "--all", "--format=%(refname:short)%09%(objectname)"])
    for line in branch_raw.splitlines():
        if "\t" not in line:
            continue
        name, tip = line.split("\t", 1)
        name = name.strip().removeprefix("remotes/")
        tip = tip.strip()
        if name.endswith("/HEAD") or name == "HEAD":
            continue
        result.branches.append(BranchInfo(
            name=name, tip=tip,
            merged_into_head=(name in merged_names or tip == result.head),
        ))

    tag_raw = _git(repo, ["tag", "--list", "--format=%(refname:short)%09%(objectname)"])
    for line in tag_raw.splitlines():
        if "\t" in line:
            name, tip = line.split("\t", 1)
            result.tags.append((name.strip(), tip.strip()))

    tree_raw = _git(repo, ["ls-tree", "-r", "--name-only", "HEAD"])
    for rel in [line.strip() for line in tree_raw.splitlines() if line.strip()]:
        full = repo / rel
        kind = _kind_for(rel)
        if not full.is_file():
            result.warnings.append(f"tracked file missing in worktree: {rel}")
            continue
        data = full.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        result.artifacts.append(Artifact(path=rel, sha256=digest, size=len(data), kind=kind))
        if kind in ("DOC", "CODE", "TEST") and len(data) <= MAX_TEXT_BYTES:
            result.texts[rel] = data.decode("utf-8", errors="replace")
    return result
