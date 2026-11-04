"""Round 4 qualification regressions: health scope, modality, doc conflicts
and explicit reporting of skipped oversized material."""

import os
import subprocess
from pathlib import Path

from necromancer.cli import investigate
from necromancer.excavator import excavate
from necromancer.models import ClaimState


def _git(repo: Path, *args: str, day: int = 1) -> str:
    env = dict(os.environ)
    stamp = f"2024-08-{day:02d}T10:00:00+00:00"
    env["GIT_AUTHOR_DATE"] = stamp
    env["GIT_COMMITTER_DATE"] = stamp
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, env=env, capture_output=True, text=True).stdout.strip()


def _make(tmp_path: Path, name: str, files: dict[str, str],
          message: str = "feat: base") -> Path:
    repo = tmp_path / name
    repo.mkdir(parents=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    for rel, content in files.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", message)
    return repo


def test_feature_abandonment_is_not_project_abandonment(tmp_path):
    repo = _make(tmp_path, "feat", {
        "README.md": "# P\n\nNote: the legacy parser was abandoned in 2023; the engine continues.\n"})
    report = investigate(str(repo))
    assert report.health["category"] != "EXPLICITLY_ABANDONED"
    assert report.health["scoped_declarations"], "feature scope must stay visible"


def test_negated_abandonment_is_not_a_declaration(tmp_path):
    repo = _make(tmp_path, "neg", {
        "README.md": "# P\n\nThis project is not abandoned; releases continue.\n"})
    report = investigate(str(repo))
    assert report.health["category"] != "EXPLICITLY_ABANDONED"
    assert report.health["declarations"] == []


def test_quoted_abandonment_is_not_a_declaration(tmp_path):
    repo = _make(tmp_path, "quote", {
        "README.md": "# P\n\n> Example of an abandoned project announcement.\n"})
    report = investigate(str(repo))
    assert report.health["category"] != "EXPLICITLY_ABANDONED"


def test_fenced_and_quoted_health_phrases_are_not_declarations(tmp_path):
    # Round 6 red team: a README showing an example announcement in a
    # code fence or quote classified the project EXPLICITLY_ABANDONED /
    # SUPERSEDED. Quoted and fenced material declares nothing.
    repo = _make(tmp_path, "fenced", {
        "README.md": "# P\n\n> This repository has been archived.\n\n```\nThis project is abandoned.\n```\n"})
    report = investigate(str(repo))
    assert report.health["category"] not in (
        "EXPLICITLY_ABANDONED", "ARCHIVED")
    repo2 = _make(tmp_path, "qsuper", {
        "README.md": "# P\n\n> Example: this tool was superseded by another.\n"})
    report2 = investigate(str(repo2))
    assert report2.health["category"] != "SUPERSEDED"


def test_project_abandonment_still_detected(tmp_path):
    repo = _make(tmp_path, "gone", {
        "README.md": "# P\n\nThis project is abandoned and no longer maintained.\n"})
    report = investigate(str(repo))
    assert report.health["category"] == "EXPLICITLY_ABANDONED"
    assert report.health["declarations"], "the exact declaration must be exposed"


def test_planned_claim_cannot_be_confirmed_contradicted(tmp_path):
    repo = _make(tmp_path, "plan", {
        "cache.py": "X = 1  # TODO later\n",
        "README.md": "# P\n\nThe redis cache layer will be implemented next sprint.\n"})
    report = investigate(str(repo))
    claim = next(c for c in report.claims if c.modality == "PLANNED")
    assert claim.state != ClaimState.CONTRADICTED
    assert all(item.qualification != "CONFIRMED"
               for item in report.contradictions
               if item.claim_id == claim.claim_id)


def test_negated_claim_agrees_with_its_stub(tmp_path):
    # Round 5 case N3: "not implemented yet" asserted absence; the stub
    # it describes was confirmed as STUB_ONLY. That inverted agreement.
    repo = _make(tmp_path, "negclaim", {
        "exporter.py": "def export():\n    raise NotImplementedError\n",
        "README.md": "# P\n\nThe export feature is not implemented yet.\n"})
    report = investigate(str(repo))
    claim = next(c for c in report.claims if "export" in c.text)
    assert claim.state == ClaimState.SUPPORTED
    assert not any(item.qualification == "CONFIRMED"
                   for item in report.contradictions
                   if item.claim_id == claim.claim_id)


def test_cross_platform_marker_is_potential_not_confirmed(tmp_path):
    # Round 5 case A4: claim scoped to Linux, marker in the Windows file.
    repo = tmp_path / "plat"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "linux_paths.py").write_text(
        "def clean(p):\n    return p.replace('..', '')\n", encoding="utf-8")
    (repo / "win_paths.py").write_text("X = 1  # TODO later\n", encoding="utf-8")
    (repo / "README.md").write_text(
        "# P\n\nFIXED path traversal on Linux.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "fix: fix path traversal on linux")
    report = investigate(str(repo))
    claim = next(c for c in report.claims if c.verb == "FIXED")
    assert claim.state != ClaimState.CONTRADICTED
    assert any(item.qualification == "POTENTIAL"
               for item in report.contradictions
               if item.claim_id == claim.claim_id)


def test_historical_claim_with_marker_is_potential(tmp_path):
    # Round 5 case A2: true in v1, marker appeared later in the same file.
    repo = tmp_path / "hist"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "validator.py").write_text(
        "def check(v):\n    return bool(v.strip())\n", encoding="utf-8")
    (repo / "README.md").write_text(
        "# P\n\nThe xss validation was fixed in v1.0.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "release v1")
    (repo / "validator.py").write_text(
        "def check(v):\n    return v  # TODO revisit\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "refactor validator")
    report = investigate(str(repo))
    claim = next(c for c in report.claims if c.modality == "HISTORICAL")
    assert claim.state != ClaimState.CONTRADICTED
    assert any(item.qualification == "POTENTIAL"
               for item in report.contradictions
               if item.claim_id == claim.claim_id)


def test_doc_antonym_conflict_is_potential(tmp_path):
    # Round 5 case A3: "complete" in one doc, "incomplete" in another,
    # sharing only the subject token.
    repo = _make(tmp_path, "docs", {
        "exporter.py": "def export():\n    return []\n",
        "README.md": "# P\n\nThe exporter is implemented and complete.\n",
        "RESEARCH.md": "# Notes\n\nThe exporter remains incomplete for large files.\n"})
    report = investigate(str(repo))
    assert any(item.kind == "DOC_CONFLICT" and item.qualification == "POTENTIAL"
               for item in report.contradictions)


def test_deprecated_wins_over_sanitize_substring(tmp_path):
    # sanitize_html contains "sanitize" but is not a SANITIZED claim;
    # verb precedence must not steal DEPRECATED claims (Round 5, P2).
    repo = _make(tmp_path, "dep", {
        "legacy.py": "def sanitize_html(v):\n    return v\n",
        "README.md": "# P\n\nsanitize_html is deprecated; use clean_html.\n"})
    report = investigate(str(repo))
    claim = next(c for c in report.claims if "sanitize_html" in c.text)
    assert claim.verb == "DEPRECATED"
    assert claim.state == ClaimState.CONTRADICTED


def test_file_only_revert_overlap_is_potential(tmp_path):
    # Round 5 VIGÍA finding: 3 real revert commits produced 683
    # REVERTED_FIX confirmations because one revert touched hundreds of
    # files. File overlap without a subject/hash tie must not confirm.
    repo = tmp_path / "fanout"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "T")
    (repo / "validator.py").write_text("def check(v):\n    return True\n", encoding="utf-8")
    (repo / "bundle.txt").write_text("v1\n", encoding="utf-8")
    (repo / "README.md").write_text("# P\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat: base")
    (repo / "validator.py").write_text("def check(v):\n    return bool(v)\n", encoding="utf-8")
    (repo / "bundle.txt").write_text("v1.1\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "fix: fix XSS validation")
    (repo / "README.md").write_text("# P\n\nFIXED xss validation.\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "docs: status")
    (repo / "bundle.txt").write_text("v2\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "chore: rename bundles")
    _git(repo, "revert", "--no-edit", "HEAD")
    report = investigate(str(repo))
    claim = next(c for c in report.claims if c.verb == "FIXED")
    assert any(
        item.kind == "REVERTED_FIX" and item.qualification == "POTENTIAL"
        for item in report.contradictions if item.claim_id == claim.claim_id), \
        "file-only revert overlap must surface as POTENTIAL, never CONFIRMED"
    assert claim.state != ClaimState.CONTRADICTED


def test_oversized_text_is_skipped_and_reported(tmp_path):
    repo = _make(tmp_path, "big", {
        "big.py": "x = '" + ("a" * 210_000) + "'\n",
        "README.md": "# P\n"})
    excavation = excavate(str(repo))
    assert excavation.stats["texts_skipped_over_cap"] == 1
    assert any("not text-indexed" in warning for warning in excavation.warnings)
    assert "big.py" not in excavation.texts
