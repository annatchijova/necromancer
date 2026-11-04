#!/usr/bin/env python3
"""Versioned epistemic-calibration benchmark (Round 4, v1).

Builds tiny synthetic repositories with known ground truth, runs the
deterministic qualification pipeline, and reports the metrics that match the
actual decision: a CONFIRMED contradiction changes a claim to CONTRADICTED
and feeds the planner, so precision is primary; recall is secondary because
misses remain visible as POTENTIAL conflicts requiring human review, never
as silent passes. Binding scores are never treated as probabilities, so no
calibration curve is applicable.

Baselines reported beside the system under test:
- never-confirm (constant negative),
- always-confirm (constant positive),
- naive-substring (pre-qualification rule: any TODO/FIXME/XXX substring
  anywhere confirms; defined over claim cases only).

Negative controls: inverted ground-truth labels must produce failures; if
the harness still passed, it would be scoring something else.

These labeled cases were inspected during development. This is a validation
set spent during tuning, NOT a held-out test set. The sample is far too
small for generalization; a Wilson 95% interval is reported to make the
uncertainty explicit. Do not quote these numbers as universal accuracy.
"""

from __future__ import annotations

import hashlib
import math
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from necromancer import health as health_mod  # noqa: E402
from necromancer.cli import investigate  # noqa: E402
from necromancer.coroner import analyze  # noqa: E402
from necromancer.excavator import excavate  # noqa: E402
from necromancer.models import ClaimState  # noqa: E402

BENCHMARK_VERSION = "round4-calibration-v1"
ENV = {**os.environ, "GIT_AUTHOR_NAME": "Bench", "GIT_AUTHOR_EMAIL": "b@x",
       "GIT_COMMITTER_NAME": "Bench", "GIT_COMMITTER_EMAIL": "b@x"}


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


def evaluate(repo: Path) -> tuple[bool, str]:
    excavation = excavate(str(repo))
    claims, _links, contradictions = analyze(excavation)
    confirmed_ids = {c.claim_id for c in contradictions
                     if c.qualification == "CONFIRMED"}
    hits = [claim for claim in claims
            if claim.state is ClaimState.CONTRADICTED
            and claim.claim_id in confirmed_ids]
    potential = sum(1 for c in contradictions
                    if c.qualification == "POTENTIAL")
    label = "CONFIRMED" if hits else f"not-confirmed(potential={potential})"
    return (bool(hits), label)


def evaluate_health(repo: Path) -> tuple[bool, str]:
    excavation = excavate(str(repo))
    report = investigate(str(repo))
    result = health_mod.analyze_health(excavation, report)
    return (result["category"] == "EXPLICITLY_ABANDONED", result["category"])


def naive_confirmed(repo: Path) -> bool:
    """Pre-qualification baseline: any marker substring anywhere confirms."""
    excavation = excavate(str(repo))
    blob = "\n".join(excavation.texts.values()).lower()
    return any(marker in blob for marker in ("todo", "fixme", "xxx"))


def case_true_incomplete_fix(repo: Path) -> None:
    commit(repo, "fix: fix XSS validation",
           {"validator.py": "def check(v):\n    return v  # TODO finish\n",
            "README.md": "# P\n\nFIXED xss validation.\n"})


def case_unrelated_marker(repo: Path) -> None:
    commit(repo, "base",
           {"validator.py": "def check(v):\n    return bool(v)\n",
            "billing.py": "X = 1  # TODO later\n",
            "README.md": "# P\n"})
    commit(repo, "fix: fix XSS validation",
           {"validator.py": "def check(v):\n    return bool(v.strip())\n",
            "README.md": "# P\n\nFIXED xss validation.\n"})


def case_reverted_fix(repo: Path) -> None:
    commit(repo, "base",
           {"validator.py": "def check(v):\n    return True\n",
            "README.md": "# P\n"})
    commit(repo, "fix: fix XSS validation",
           {"validator.py": "def check(v):\n    return bool(v)\n",
            "README.md": "# P\n\nFIXED xss validation.\n"})
    git(repo, "revert", "--no-edit", "HEAD")
    commit(repo, "docs", {"README.md": "# P\n\nFIXED xss validation.\n"})


def case_planned_vs_marker(repo: Path) -> None:
    commit(repo, "plan",
           {"cache.py": "X = 1  # TODO later\n",
            "README.md": "# P\n\nThe redis cache layer will be implemented next sprint.\n"})


def case_same_file_marker(repo: Path) -> None:
    commit(repo, "fix: fix XSS validation",
           {"validator.py": "def check(v):\n    return v  # TODO finish\n",
            "README.md": "# P\n"})


def case_commit_claim_unrelated_marker(repo: Path) -> None:
    commit(repo, "base",
           {"validator.py": "def check(v):\n    return bool(v)\n",
            "billing.py": "X = 1  # TODO later\n", "README.md": "# P\n"})
    commit(repo, "fix: fix XSS validation",
           {"validator.py": "def check(v):\n    return bool(v.strip())\n"})


def case_health_feature_abandoned(repo: Path) -> None:
    commit(repo, "docs",
           {"README.md": "# P\n\nNote: the legacy parser was abandoned in 2023; the engine continues.\n"})


def case_health_negated(repo: Path) -> None:
    commit(repo, "docs",
           {"README.md": "# P\n\nThis project is not abandoned; releases continue.\n"})


def case_health_quoted(repo: Path) -> None:
    commit(repo, "docs",
           {"README.md": "# P\n\n> Example of an abandoned project announcement.\n"})


def case_health_explicit_project(repo: Path) -> None:
    commit(repo, "docs",
           {"README.md": "# P\n\nThis project is abandoned and no longer maintained.\n"})


CASES: list[tuple[str, str, str, bool, str]] = [
    # (name, category, kind, expect_positive, ground-truth rationale)
    ("true-incomplete-fix", "true_contradiction", "claim", True,
     "FIXED claim; the bound fix leaves a strict marker in a file it changed."),
    ("unrelated-marker", "false_contradiction", "claim", False,
     "FIXED claim; marker lives in a module the fix never touched."),
    ("reverted-fix", "regression", "claim", True,
     "Fix later reverted; the defect is present again at HEAD."),
    ("planned-vs-marker", "modality_mismatch", "claim", False,
     "A PROPOSED feature with a marker is a plan, not a broken promise."),
    ("same-file-marker", "true_contradiction", "claim", True,
     "Commit claim; strict marker in a file that same commit changed."),
    ("commit-claim-unrelated-marker", "false_contradiction", "claim", False,
     "Commit FIXED claim; marker only in an untouched module."),
    ("health-feature-abandoned", "abandonment_scope", "health", False,
     "A named legacy component was abandoned; the project itself was not."),
    ("health-negated", "abandonment_negation", "health", False,
     "Negated sentence: the project states it is not abandoned."),
    ("health-quoted", "abandonment_quotation", "health", False,
     "Quoted external text is not a project declaration."),
    ("health-explicit-project", "abandonment_explicit", "health", True,
     "Root README declares the project itself abandoned."),
]

BUILDERS = {
    "true-incomplete-fix": case_true_incomplete_fix,
    "unrelated-marker": case_unrelated_marker,
    "reverted-fix": case_reverted_fix,
    "planned-vs-marker": case_planned_vs_marker,
    "same-file-marker": case_same_file_marker,
    "commit-claim-unrelated-marker": case_commit_claim_unrelated_marker,
    "health-feature-abandoned": case_health_feature_abandoned,
    "health-negated": case_health_negated,
    "health-quoted": case_health_quoted,
    "health-explicit-project": case_health_explicit_project,
}


def wilson(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 1.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def confusion(rows: list[tuple[bool, bool]]) -> tuple[int, int, int, int]:
    tp = sum(1 for exp, got in rows if exp and got)
    fp = sum(1 for exp, got in rows if not exp and got)
    tn = sum(1 for exp, got in rows if not exp and not got)
    fn = sum(1 for exp, got in rows if exp and not got)
    return tp, fp, tn, fn


def rates(tp: int, fp: int, tn: int, fn: int) -> dict[str, float]:
    return {
        "precision": tp / (tp + fp) if (tp + fp) else 1.0,
        "recall": tp / (tp + fn) if (tp + fn) else 1.0,
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
        "fnr": fn / (fn + tp) if (fn + tp) else 0.0,
    }


def main() -> int:
    rows: list[tuple[str, str, str, bool, bool, str]] = []
    naive_rows: list[tuple[bool, bool]] = []
    with tempfile.TemporaryDirectory(prefix="necromancer-calibration-") as tmp:
        root = Path(tmp)
        for name, category, kind, expect, _rationale in CASES:
            repo = fresh(root, name)
            BUILDERS[name](repo)
            if kind == "health":
                got, label = evaluate_health(repo)
            else:
                got, label = evaluate(repo)
                naive_rows.append((expect, naive_confirmed(repo)))
            rows.append((name, category, kind, expect, got, label))

    digest = hashlib.sha256(
        "|".join(case[0] + case[4] for case in CASES).encode()).hexdigest()[:16]
    print(f"benchmark={BENCHMARK_VERSION} case_set_sha256={digest}")
    print("test_set_status=validation-spent-during-development (not held-out)")
    print()
    for name, category, kind, expect, got, label in rows:
        ok = got == expect
        print(f"{'PASS' if ok else 'FAIL'}  {name:32s} [{category}/{kind}] "
              f"expected_positive={expect} observed={label}")

    pairs = [(expect, got) for _n, _c, _k, expect, got, _l in rows]
    tp, fp, tn, fn = confusion(pairs)
    system = rates(tp, fp, tn, fn)
    p_lo, p_hi = wilson(tp, tp + fp)
    r_lo, r_hi = wilson(tp, tp + fn)
    print()
    print(f"system            tp={tp} fp={fp} tn={tn} fn={fn}")
    print(f"precision={system['precision']:.3f} [95% Wilson {p_lo:.3f}-{p_hi:.3f}] "
          f"recall={system['recall']:.3f} [95% Wilson {r_lo:.3f}-{r_hi:.3f}] "
          f"fpr={system['fpr']:.3f} fnr={system['fnr']:.3f}")

    for label, baseline_pairs in (
        ("never-confirm(claims-only)", [(exp, False) for exp, _g in naive_rows]),
        ("always-confirm(claims-only)", [(exp, True) for exp, _g in naive_rows]),
        ("naive-substring(claims-only)", naive_rows),
    ):
        b_tp, b_fp, b_tn, b_fn = confusion(baseline_pairs)
        b = rates(b_tp, b_fp, b_tn, b_fn)
        print(f"baseline {label:28s} precision={b['precision']:.3f} "
              f"recall={b['recall']:.3f} fpr={b['fpr']:.3f}")

    print()
    print("by category:")
    categories = sorted({row[1] for row in rows})
    worst: tuple[str, float] | None = None
    for category in categories:
        sub = [(exp, got) for _n, c, _k, exp, got, _l in rows if c == category]
        s_tp, s_fp, s_tn, s_fn = confusion(sub)
        total = len(sub)
        passed = s_tp + s_tn
        frac = passed / total if total else 0.0
        if worst is None or frac < worst[1]:
            worst = (category, frac)
        print(f"  {category:24s} {passed}/{total} correct")
    if worst:
        print(f"worst slice: {worst[0]} ({worst[1]:.3f})")

    # Negative control: inverted labels must fail. A harness that passes
    # under inverted ground truth is scoring something other than the cases.
    inverted_failures = sum(1 for _n, _c, _k, exp, got, _l in rows
                            if got == exp)
    print()
    print(f"negative_control inverted-labels: {inverted_failures}/{len(rows)} "
          "cases fail as required (harness can produce a bad score)")

    print()
    print("limitations: n is tiny, cases were spent during development, and "
          "synthetic ground truth cannot represent real-repository ambiguity. "
          "Offline blind spots: distribution shift to real histories, "
          "selection bias toward known failure modes, and errors never "
          "exercised because no case encodes them.")
    all_ok = all(got == expect for _n, _c, _k, expect, got, _l in rows)
    control_ok = inverted_failures == len(rows)
    return 0 if (all_ok and control_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
