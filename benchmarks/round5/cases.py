#!/usr/bin/env python3
"""Round 5 independent evaluation set: case construction ONLY.

This module defines labeled cases and builds their fixture repositories.
It never runs NECROMANCER. Labels were written from the construction of
each fixture (what was deliberately planted), before any prediction was
observed. Provenance of every label: same-agent construction, NOT
independent human adjudication. Ambiguous cases are labeled POTENTIAL
and preserved as ambiguous; they are not forced into true/false.

Freeze procedure: `python benchmarks/round5/run_evaluation.py --freeze`
hashes this file's case definitions into the run output. Any later edit
changes the hash and invalidates comparisons against earlier runs.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path

ENV = {**os.environ, "GIT_AUTHOR_NAME": "Eval", "GIT_AUTHOR_EMAIL": "e@x",
       "GIT_COMMITTER_NAME": "Eval", "GIT_COMMITTER_EMAIL": "e@x"}


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, env=ENV,
                   capture_output=True, text=True)


def commit(repo: Path, message: str, files: dict[str, str]) -> None:
    for name, content in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", message)


def fresh(root: Path, name: str) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    git(repo, "init", "-b", "main")
    return repo


# Each case: id, category, expected (CONFIRMED | POTENTIAL | NONE),
# target (substring selecting the claim under evaluation),
# rationale (why the label is what it is, from construction).
CASES: list[dict] = [
    dict(id="P1-direct-incomplete", category="direct_contradiction",
         expected="CONFIRMED", target="xss",
         rationale="FIXED claim; bound fix leaves a strict marker in the file it changed."),
    dict(id="P2-deprecated-still-present", category="direct_contradiction",
         expected="CONFIRMED", target="sanitize_html",
         rationale="Deprecation claimed; the deprecated token is still present in current code."),
    dict(id="P3-reverted-fix", category="regression",
         expected="CONFIRMED", target="xss",
         rationale="Fix committed, then reverted; defect present again at HEAD."),
    dict(id="P4-narrower-implementation", category="scope_mismatch_fn",
         expected="CONFIRMED", target="validated",
         rationale="Docs guarantee ALL input validated; implementation validates one field only. Planted as a genuine contradiction the lexical engine is expected to miss."),
    dict(id="P5-different-wording", category="vocabulary_mismatch_fn",
         expected="CONFIRMED", target="sanitized",
         rationale="Claim says output is sanitized; the sanitizer is a pass-through stub under different vocabulary. Planted genuine contradiction, likely missed."),
    dict(id="N1-unrelated-marker", category="false_contradiction",
         expected="NONE", target="xss",
         rationale="Marker lives in a module the fix never touched."),
    dict(id="N2-spanish-prose", category="multilingual",
         expected="NONE", target="xss",
         rationale="Spanish prose contains 'todo' as an ordinary word, not a marker."),
    dict(id="N3-negated-statement", category="negation",
         expected="NONE", target="export",
         rationale="Documentation states the feature is NOT implemented; code agrees (stub). Agreement, not contradiction."),
    dict(id="N4-execution-required", category="execution_required",
         expected="NONE", target="verified",
         rationale="Claim says verified by tests; no execution evidence exists. Absence of evidence is not a contradiction."),
    dict(id="N5-no-fix-commit", category="insufficient_evidence",
         expected="NONE", target="xss",
         rationale="FIXED claimed in docs; no fix commit exists. Unsupported, not contradicted."),
    dict(id="N6-quoted-claim", category="quotation",
         expected="NONE", target="xss",
         rationale="The fixed claim appears inside a quoted example; a clean fix exists in code."),
    dict(id="A1-planned-feature", category="modality",
         expected="POTENTIAL", target="redis",
         rationale="Future plan with an incomplete marker: a plan cannot be contradicted by current code, but the tension deserves review."),
    dict(id="A2-historical-claim", category="temporal",
         expected="POTENTIAL", target="xss",
         rationale="Claim was true in v1; code later changed. Historical truth is not a current contradiction."),
    dict(id="A3-doc-scope-conflict", category="documentation_scope",
         expected="POTENTIAL", target="exporter",
         rationale="Two documents disagree about the exporter with different scopes; sentence-level conflict, not established code contradiction."),
    dict(id="A4-platform-specific", category="platform_scope",
         expected="POTENTIAL", target="path traversal",
         rationale="Claim is about the Linux path; marker sits in the Windows-only module. Scope cannot be aligned automatically."),
    dict(id="A5-shared-evidence", category="shared_evidence",
         expected="CONFIRMED", target="xss validation",
         rationale="Three claims share vocabulary; only the XSS claim is bound to the file carrying the marker. The target claim is genuinely contradicted; siblings must not be."),
]


def build(case_id: str, repo: Path) -> None:
    if case_id == "P1-direct-incomplete":
        commit(repo, "fix: fix XSS validation",
               {"validator.py": "def check(v):\n    return v  # TODO finish\n",
                "README.md": "# P\n\nFIXED xss validation.\n"})
    elif case_id == "P2-deprecated-still-present":
        commit(repo, "base",
               {"legacy.py": "def sanitize_html(v):\n    return v\n",
                "README.md": "# P\n\nsanitize_html is deprecated; use clean_html.\n"})
    elif case_id == "P3-reverted-fix":
        commit(repo, "base",
               {"validator.py": "def check(v):\n    return True\n", "README.md": "# P\n"})
        commit(repo, "fix: fix XSS validation",
               {"validator.py": "def check(v):\n    return bool(v)\n",
                "README.md": "# P\n\nFIXED xss validation.\n"})
        git(repo, "revert", "--no-edit", "HEAD")
        commit(repo, "docs", {"README.md": "# P\n\nFIXED xss validation.\n"})
    elif case_id == "P4-narrower-implementation":
        commit(repo, "feat: input handling",
               {"store.py": "def store(name, bio, url):\n    assert name.isalnum()\n    save(name, bio, url)\n",
                "README.md": "# P\n\nAll user input is validated before storage.\n"})
    elif case_id == "P5-different-wording":
        commit(repo, "feat: output encoding",
               {"encoding.py": "def sanitize_output(v):\n    return v\n",
                "README.md": "# P\n\nUser output is sanitized before rendering.\n"})
    elif case_id == "N1-unrelated-marker":
        commit(repo, "base",
               {"validator.py": "def check(v):\n    return bool(v)\n",
                "billing.py": "X = 1  # TODO later\n", "README.md": "# P\n"})
        commit(repo, "fix: fix XSS validation",
               {"validator.py": "def check(v):\n    return bool(v.strip())\n",
                "README.md": "# P\n\nFIXED xss validation.\n"})
    elif case_id == "N2-spanish-prose":
        commit(repo, "fix: fix XSS validation",
               {"validator.py": "def check(v):\n    # todo el sistema valida la entrada\n    return bool(v)\n",
                "README.md": "# P\n\nFIXED xss validation.\n"})
    elif case_id == "N3-negated-statement":
        commit(repo, "base",
               {"exporter.py": "def export():\n    raise NotImplementedError\n",
                "README.md": "# P\n\nThe export feature is not implemented yet.\n"})
    elif case_id == "N4-execution-required":
        commit(repo, "base",
               {"validator.py": "def check(v):\n    return bool(v)\n",
                "README.md": "# P\n\nThe xss fix was verified by the full test suite.\n"})
    elif case_id == "N5-no-fix-commit":
        commit(repo, "docs",
               {"validator.py": "def check(v):\n    return bool(v)\n",
                "README.md": "# P\n\nFIXED xss validation.\n"})
    elif case_id == "N6-quoted-claim":
        commit(repo, "fix: fix XSS validation",
               {"validator.py": "def check(v):\n    return bool(v.strip())\n",
                "README.md": "# P\n\n> Example announcement: the xss issue was fixed.\n"})
    elif case_id == "A1-planned-feature":
        commit(repo, "plan",
               {"cache.py": "X = 1  # TODO later\n",
                "README.md": "# P\n\nThe redis cache layer will be implemented next sprint.\n"})
    elif case_id == "A2-historical-claim":
        commit(repo, "release v1",
               {"validator.py": "def check(v):\n    return bool(v.strip())\n",
                "README.md": "# P\n\nThe xss validation was fixed in v1.0.\n"})
        commit(repo, "refactor validator",
               {"validator.py": "def check(v):\n    return v  # TODO revisit\n"})
    elif case_id == "A3-doc-scope-conflict":
        commit(repo, "docs",
               {"exporter.py": "def export():\n    return []\n",
                "README.md": "# P\n\nThe exporter is implemented and complete.\n",
                "RESEARCH.md": "# Notes\n\nThe exporter remains incomplete for large files.\n"})
    elif case_id == "A4-platform-specific":
        commit(repo, "fix: fix path traversal on linux",
               {"linux_paths.py": "def clean(p):\n    return p.replace('..', '')\n",
                "win_paths.py": "X = 1  # TODO later\n",
                "README.md": "# P\n\nFIXED path traversal on Linux.\n"})
    elif case_id == "A5-shared-evidence":
        commit(repo, "base",
               {"validator.py": "def check(v):\n    return bool(v)\n",
                "billing.py": "def bill():\n    return 0  # TODO later\n",
                "README.md": "# P\n"})
        commit(repo, "fix: fix XSS validation",
               {"validator.py": "def check(v):\n    return v  # TODO finish\n",
                "README.md": "# P\n\nFIXED xss validation. FIXED billing totals. FIXED export totals.\n"})
    else:  # pragma: no cover
        raise KeyError(case_id)


def case_set_hash() -> str:
    payload = "|".join(
        f"{c['id']}:{c['expected']}:{c['target']}:{c['rationale']}" for c in CASES)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
