"""Secure acquisition of public GitHub repositories.

Only https://github.com/<owner>/<repo> is accepted. Acquisition failures
are reported as AcquisitionError, never dressed up as forensic findings.
The clone runs without a shell, without credentials, without submodules
and without checkout hooks; content stays untrusted data.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

MAX_REPO_BYTES = 200 * 1024 * 1024
MAX_DEPTH = 500
CLONE_TIMEOUT_SECONDS = 120
_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,99}$")


class AcquisitionError(RuntimeError):
    pass


def parse_github_url(raw: str) -> tuple[str, str, str]:
    """Return (owner, repo, canonical clone URL) or raise AcquisitionError."""
    if not isinstance(raw, str) or not raw.strip():
        raise AcquisitionError("repository URL must be a non-empty string")
    if any(char in raw for char in (" ", "\t", "\n", ";", "|", "&", "$", "`", "\\")):
        raise AcquisitionError("repository URL contains forbidden characters")
    parsed = urlparse(raw.strip())
    if parsed.scheme != "https":
        raise AcquisitionError("only https GitHub URLs are accepted")
    if parsed.hostname != "github.com":
        raise AcquisitionError("only github.com hosts are accepted")
    if parsed.port is not None or parsed.username or parsed.password:
        raise AcquisitionError("ports and credentials in URLs are forbidden")
    if parsed.query or parsed.fragment:
        raise AcquisitionError("query strings and fragments are forbidden")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise AcquisitionError("expected https://github.com/<owner>/<repo>")
    owner, repo = parts
    if repo.endswith(".git"):
        repo = repo[:-4]
    if not _NAME.match(owner) or not _NAME.match(repo):
        raise AcquisitionError("invalid owner or repository name")
    if owner in (".", "..") or repo in (".", "..") or ".." in owner or ".." in repo:
        raise AcquisitionError("path traversal in repository URL")
    return owner, repo, f"https://github.com/{owner}/{repo}.git"


def _default_runner(clone_url: str, dest: Path) -> None:
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    proc = subprocess.run(
        [
            "git", "-c", "credential.helper=", "clone", "--quiet",
            "--no-checkout", "--single-branch",
            f"--depth={MAX_DEPTH}", "--no-recurse-submodules",
            clone_url, str(dest),
        ],
        capture_output=True, text=True, timeout=CLONE_TIMEOUT_SECONDS,
        env=env, check=False,
    )
    if proc.returncode != 0:
        raise AcquisitionError(
            f"git clone failed: {proc.stderr.strip()[:300] or 'unknown error'}")


def _tree_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                continue
    return total


def acquire_github(raw_url: str, base: Path | None = None, runner=None) -> Path:
    """Clone into an isolated workspace and return the repository path.

    The runner is injectable so acquisition limits can be tested with
    controlled fixtures and no network. On any failure the partial
    workspace is removed.
    """
    owner, repo, clone_url = parse_github_url(raw_url)
    root = Path(base) if base else Path(tempfile.gettempdir()) / "necromancer-acquisitions"
    root.mkdir(parents=True, exist_ok=True)
    dest = Path(tempfile.mkdtemp(prefix=f"{owner}-{repo}-", dir=root))
    try:
        (runner or _default_runner)(clone_url, dest)
        if not (dest / ".git").exists():
            raise AcquisitionError("clone produced no repository (acquisition failure)")
        size = _tree_size(dest)
        if size > MAX_REPO_BYTES:
            raise AcquisitionError(
                f"repository exceeds acquisition size limit ({size} > {MAX_REPO_BYTES} bytes)")
        return dest
    except BaseException:
        shutil.rmtree(dest, ignore_errors=True)
        raise
