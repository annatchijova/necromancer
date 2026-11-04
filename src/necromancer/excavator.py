"""Read-only Git excavation. The target repository is untrusted data.

Only allowlisted, read-only Git subcommands run, with optional locks
disabled. Repository code is never executed and the target is never
written to.
"""

from __future__ import annotations

import hashlib
import io
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .models import Artifact, BranchInfo, CommitRecord

ALLOWED_SUBCOMMANDS = frozenset(
    {"log", "show", "branch", "tag", "rev-parse", "ls-tree", "merge-base", "rev-list", "cat-file"}
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


class ExcavationCancelled(RuntimeError):
    """Raised when the caller's cancellation event is set."""


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
    # Snapshot scope: every artifact hash and text describes exactly this
    # scope. "head" reads committed blobs; "worktree" reads the files on
    # disk and reports how they diverge from HEAD.
    snapshot: str = "head"
    divergent_files: list[str] = field(default_factory=list)
    stats: dict = field(default_factory=dict)


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


def _git_bytes(repo: Path, args: list[str]) -> bytes:
    if not args or args[0] not in ALLOWED_SUBCOMMANDS:
        raise ExcavationError(f"git subcommand not allowlisted: {args[:1]}")
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    env["PAGER"] = "cat"
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, timeout=60, env=env, check=False,
    )
    if proc.returncode != 0:
        raise ExcavationError(f"git {' '.join(args[:2])} failed")
    return proc.stdout


def _consume(stream) -> tuple[str, int, bytes | None]:
    """Hash a byte stream incrementally; retain text only up to the cap."""
    digest = hashlib.sha256()
    size = 0
    buffer = bytearray()
    keep = True
    while True:
        chunk = stream.read(1 << 20)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
        if keep:
            if size <= MAX_TEXT_BYTES:
                buffer.extend(chunk)
            else:
                keep = False
                buffer = bytearray()
    return digest.hexdigest(), size, (bytes(buffer) if keep else None)


def _head_blob(repo: Path, rel: str) -> tuple[str, int, bytes | None]:
    env = dict(os.environ)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_PAGER"] = "cat"
    proc = subprocess.Popen(
        ["git", "-C", str(repo), "cat-file", "blob", f"HEAD:{rel}"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=env,
    )
    assert proc.stdout is not None
    result = _consume(proc.stdout)
    if proc.wait() != 0:
        raise ExcavationError(f"cannot read HEAD blob: {rel}")
    return result


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


def excavate(raw_path: str, snapshot: str = "head", progress=None,
             cancel_event=None, max_commits: int = MAX_COMMITS) -> Excavation:
    if snapshot not in ("head", "worktree"):
        raise ExcavationError(f"snapshot must be 'head' or 'worktree', got {snapshot!r}")
    repo = resolve_repo(raw_path)
    result = Excavation(repo_path=str(repo), head="", current_branch="", snapshot=snapshot)

    def _cancelled() -> None:
        if cancel_event is not None and cancel_event.is_set():
            raise ExcavationCancelled("excavation cancelled by caller")

    def _progress(stage: str, count: int) -> None:
        if progress is not None:
            progress(stage, count)
    result.head = _git(repo, ["rev-parse", "HEAD"]).strip()
    result.current_branch = _git(repo, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    if (repo / ".git" / "shallow").exists():
        result.warnings.append(
            "shallow clone: history is incomplete; missing history is reported "
            "as missing evidence, never as proof that events did not happen"
        )

    fmt = "%H%x1f%P%x1f%an%x1f%aI%x1f%s%x1f%b%x1e"
    # One streaming pass for the whole history (Round 4 scale work):
    # a subprocess per commit does not survive large repositories.
    raw_log = _git(repo, ["log", "--all", f"--max-count={max_commits}",
                          "--name-status", f"--format={fmt}"])
    records = [chunk for chunk in raw_log.split("\x1e") if chunk.strip()]
    if len(records) >= max_commits:
        result.warnings.append(f"commit history truncated at {max_commits} commits")
    # The record separator terminates the format block, so each commit's
    # name-status lines lead the *next* chunk. Attribute them backwards.
    for chunk in records:
        _cancelled()
        lines = chunk.strip("\n").splitlines()
        index = 0
        leading_files: list[tuple[str, str]] = []
        while index < len(lines) and "\t" in lines[index] and "\x1f" not in lines[index]:
            fields = lines[index].split("\t")
            leading_files.append((fields[0].strip(), fields[-1].strip()))
            index += 1
        if leading_files and result.commits:
            previous = result.commits[-1]
            result.commits[-1] = CommitRecord(
                commit_hash=previous.commit_hash, parents=previous.parents,
                author=previous.author, date_iso=previous.date_iso,
                subject=previous.subject, body=previous.body,
                files=tuple(leading_files))
        if index >= len(lines):
            continue
        parts = lines[index].split("\x1f")
        if len(parts) < 6:
            continue
        body_lines = [parts[5]] if parts[5] else []
        body_lines.extend(
            line for line in lines[index + 1:] if "\t" not in line and line)
        result.commits.append(CommitRecord(
            commit_hash=parts[0].strip(),
            parents=tuple(parts[1].split()) if parts[1].strip() else (),
            author=parts[2], date_iso=parts[3], subject=parts[4],
            body="\n".join(body_lines).strip(), files=(),
        ))
    _progress("commits", len(result.commits))

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

    # -z keeps hostile filenames (newlines, quotes) exact instead of quoted.
    tree_raw = _git(repo, ["ls-tree", "-r", "-z", "--name-only", "HEAD"])
    skipped_text = 0
    for index, rel in enumerate([item for item in tree_raw.split("\0") if item]):
        _cancelled()
        if index % 50 == 0:
            _progress("files", index)
        kind = _kind_for(rel)
        if snapshot == "head":
            # Committed blobs only, streamed: uncommitted worktree edits can
            # never leak into a HEAD investigation, and huge blobs are never
            # loaded whole into memory.
            try:
                digest, size, text_bytes = _head_blob(repo, rel)
            except ExcavationError:
                result.warnings.append(f"tracked file unreadable at HEAD: {rel}")
                continue
        else:
            full = repo / rel
            if not full.is_file():
                result.warnings.append(f"tracked file missing in worktree: {rel}")
                continue
            if full.is_symlink():
                # Never follow a tracked symlink out of the repository: its
                # evidence content is the link target string, as in Git.
                digest, size, text_bytes = _consume(
                    io.BytesIO(os.readlink(full).encode("utf-8")))
            else:
                with full.open("rb") as handle:
                    digest, size, text_bytes = _consume(handle)
            try:
                head_digest, _head_size, _head_text = _head_blob(repo, rel)
            except ExcavationError:
                head_digest = digest
            if digest != head_digest:
                result.divergent_files.append(rel)
        result.artifacts.append(Artifact(path=rel, sha256=digest, size=size, kind=kind))
        if kind in ("DOC", "CODE", "TEST"):
            if text_bytes is not None:
                result.texts[rel] = text_bytes.decode("utf-8", errors="replace")
            else:
                skipped_text += 1
    result.stats = {
        "commits": len(result.commits),
        "artifacts": len(result.artifacts),
        "texts_indexed": len(result.texts),
        "texts_skipped_over_cap": skipped_text,
        "history_truncated": len(records) >= max_commits,
    }
    if skipped_text:
        result.warnings.append(
            f"{skipped_text} file(s) hashed but not text-indexed (size cap); "
            "claims about them degrade to UNVERIFIED, never to silence")
    if snapshot == "worktree":
        result.warnings.append(
            "snapshot=worktree: file contents include uncommitted changes; "
            "untracked files are not part of the snapshot"
        )
        if result.divergent_files:
            result.warnings.append(
                f"snapshot=worktree: {len(result.divergent_files)} tracked file(s) "
                f"differ from HEAD: {', '.join(sorted(result.divergent_files)[:8])}"
            )
    return result
