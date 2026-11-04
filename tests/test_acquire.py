"""GitHub acquisition: strict parsing, bounded clone, clean failures."""

import shutil
from pathlib import Path

import pytest

from necromancer.acquire import AcquisitionError, acquire_github, parse_github_url


@pytest.mark.parametrize("raw", [
    "http://github.com/owner/repo",
    "https://evil.example/owner/repo",
    "https://github.com.evil.example/owner/repo",
    "https://user:pass@github.com/owner/repo",
    "https://github.com:8443/owner/repo",
    "https://github.com/owner/repo?x=1",
    "https://github.com/owner/repo#frag",
    "https://github.com/owner",
    "https://github.com/../repo",
    "https://github.com/owner/re po",
    "https://github.com/owner/repo;rm -rf",
    "git@github.com:owner/repo",
    "file:///etc/passwd",
    "",
])
def test_rejects_non_github_or_malformed_urls(raw):
    with pytest.raises(AcquisitionError):
        parse_github_url(raw)


def test_accepts_canonical_github_urls():
    assert parse_github_url("https://github.com/annatchijova/necromancer") == (
        "annatchijova", "necromancer",
        "https://github.com/annatchijova/necromancer.git")
    assert parse_github_url("https://github.com/owner/repo.git")[1] == "repo"


def test_acquire_with_controlled_runner(synthetic, tmp_path):
    source = Path(synthetic["a"])

    def fake_runner(clone_url: str, dest: Path) -> None:
        shutil.copytree(source, dest, dirs_exist_ok=True)

    dest = acquire_github(
        "https://github.com/example/fixture-a", base=tmp_path / "acq", runner=fake_runner)
    assert (dest / ".git").exists()
    assert dest.parent == tmp_path / "acq"


def test_failed_acquisition_cleans_up_and_stays_an_error(tmp_path):
    def broken_runner(clone_url: str, dest: Path) -> None:
        (dest / "partial.txt").write_text("partial", encoding="utf-8")
        raise AcquisitionError("network down (simulated)")

    base = tmp_path / "acq"
    with pytest.raises(AcquisitionError):
        acquire_github("https://github.com/example/nope", base=base, runner=broken_runner)
    assert list(base.iterdir()) == [], "interrupted acquisition must not leave a workspace"
