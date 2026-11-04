#!/usr/bin/env python3
"""Round 5 evaluation runner.

Freezes the case set from cases.py (hash printed on every run), builds
each fixture, and evaluates, on the SAME frozen cases:

- Baseline A: never confirm.
- Baseline B: always confirm (over cases where a target claim exists).
- Baseline C: naive-substring reconstruction (the pre-qualification rule,
  approximated at claim level: strictness OFF, any TODO/FIXME/XXX
  substring anywhere in the indexed texts confirms the target claim).
  This is a reconstruction, not the historical binary; labeled as such.
- System D: current NECROMANCER qualification (working tree, after
  any Round 5 repairs; the pre-repair run is recorded in
  docs/EPISTEMIC-CALIBRATION.md, not hidden).

Three-way labels: CONFIRMED / POTENTIAL / NONE. POTENTIAL is an
abstention, reported separately and never silently collapsed: binary
metrics use the documented mapping CONFIRMED vs {POTENTIAL, NONE}, and
selective metrics are computed on decided (non-POTENTIAL) cases only.

Labels are same-agent constructions from fixture planting, frozen before
evaluation. This is NOT independent human ground truth.
"""

from __future__ import annotations

import math
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import cases as case_mod  # noqa: E402
from necromancer.cli import investigate  # noqa: E402
from necromancer.excavator import excavate  # noqa: E402
from necromancer.models import ClaimState  # noqa: E402

LABELS = ("CONFIRMED", "POTENTIAL", "NONE")


def predict_current(repo: Path, target: str) -> tuple[str, str]:
    report = investigate(str(repo))
    matches = [c for c in report.claims if target.lower() in c.text.lower()]
    if not matches:
        return "NONE", "no target claim extracted"
    claim = matches[0]
    items = [c for c in report.contradictions if c.claim_id == claim.claim_id]
    detail = "; ".join(
        f"{i.kind}/{i.qualification}" for i in items) or f"state={claim.state.value}"
    if any(i.qualification == "CONFIRMED" for i in items) \
            and claim.state is ClaimState.CONTRADICTED:
        return "CONFIRMED", detail
    if items:
        return "POTENTIAL", detail
    return "NONE", detail


def predict_naive(repo: Path, target: str) -> tuple[str, str]:
    excavation = excavate(str(repo))
    report = investigate(str(repo))
    matches = [c for c in report.claims if target.lower() in c.text.lower()]
    if not matches:
        return "NONE", "no target claim extracted"
    blob = "\n".join(excavation.texts.values()).lower()
    if any(marker in blob for marker in ("todo", "fixme", "xxx")):
        return "CONFIRMED", "naive: marker substring present somewhere"
    return "NONE", "naive: no marker substring"


def wilson(successes: int, total: int, z: float = 1.96) -> str:
    if total == 0:
        return "undefined (n=0)"
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return f"{p:.3f} [95% Wilson {max(0.0, centre - half):.3f}-{min(1.0, centre + half):.3f}] (n={total})"


def binary_metrics(pairs: list[tuple[str, str]]) -> dict:
    tp = sum(1 for e, p in pairs if e == "CONFIRMED" and p == "CONFIRMED")
    fp = sum(1 for e, p in pairs if e != "CONFIRMED" and p == "CONFIRMED")
    tn = sum(1 for e, p in pairs if e != "CONFIRMED" and p != "CONFIRMED")
    fn = sum(1 for e, p in pairs if e == "CONFIRMED" and p != "CONFIRMED")
    decided = [(e, p) for e, p in pairs if p != "POTENTIAL"]
    d_tp = sum(1 for e, p in decided if e == "CONFIRMED" and p == "CONFIRMED")
    d_fp = sum(1 for e, p in decided if e != "CONFIRMED" and p == "CONFIRMED")
    d_fn = sum(1 for e, p in decided if e == "CONFIRMED" and p != "CONFIRMED")
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": wilson(tp, tp + fp) if (tp + fp) else f"undefined (no confirms)",
        "recall": wilson(tp, tp + fn) if (tp + fn) else "undefined (no positives)",
        "fpr": f"{fp / (fp + tn):.3f}" if (fp + tn) else "undefined",
        "fnr": f"{fn / (fn + tp):.3f}" if (fn + tp) else "undefined",
        "coverage": f"{len(decided) / len(pairs):.3f}" if pairs else "undefined",
        "abstention": f"{(len(pairs) - len(decided)) / len(pairs):.3f}" if pairs else "undefined",
        "selective_precision": wilson(d_tp, d_tp + d_fp) if (d_tp + d_fp) else "undefined (no decided confirms)",
        "selective_recall": wilson(d_tp, d_tp + d_fn) if (d_tp + d_fn) else "undefined (no decided positives)",
    }


def main() -> int:
    frozen = case_mod.case_set_hash()
    print(f"dataset=round5-evaluation-v1 case_set_sha256={frozen}")
    print("label_provenance=same-agent construction, frozen before evaluation; "
          "NOT independent human ground truth")
    systems: dict[str, list[tuple[str, str]]] = {
        "A-never": [], "B-always": [], "C-naive(reconstructed)": [], "D-current": [],
    }
    rows = []
    with tempfile.TemporaryDirectory(prefix="necromancer-round5-") as tmp:
        root = Path(tmp)
        for case in case_mod.CASES:
            repo = case_mod.fresh(root, case["id"])
            case_mod.build(case["id"], repo)
            current, detail = predict_current(repo, case["target"])
            naive, _ = predict_naive(repo, case["target"])
            report = investigate(str(repo))
            has_target = any(
                case["target"].lower() in c.text.lower() for c in report.claims)
            systems["A-never"].append((case["expected"], "NONE"))
            systems["B-always"].append(
                (case["expected"], "CONFIRMED" if has_target else "NONE"))
            systems["C-naive(reconstructed)"].append((case["expected"], naive))
            systems["D-current"].append((case["expected"], current))
            rows.append((case, current, detail))
    print()
    for case, current, detail in rows:
        mark = "PASS" if current == case["expected"] else "MISS"
        print(f"{mark}  {case['id']:28s} [{case['category']}] "
              f"expected={case['expected']:9s} predicted={current:9s} ({detail})")
    for name, pairs in systems.items():
        confusion = Counter(pairs)
        matrix = {e: {p: confusion.get((e, p), 0) for p in LABELS} for e in LABELS}
        m = binary_metrics(pairs)
        print()
        print(f"== {name}")
        print(f"   confusion(expected x predicted): {matrix}")
        print(f"   tp={m['tp']} fp={m['fp']} tn={m['tn']} fn={m['fn']} "
              f"precision={m['precision']} recall={m['recall']} "
              f"fpr={m['fpr']} fnr={m['fnr']}")
        print(f"   coverage={m['coverage']} abstention={m['abstention']} "
              f"selective_precision={m['selective_precision']} "
              f"selective_recall={m['selective_recall']}")
    print()
    print("by category (D-current):")
    cats = sorted({case["category"] for case, _c, _d in rows})
    worst = None
    for cat in cats:
        sub = [(case["expected"], cur) for case, cur, _d in rows
               if case["category"] == cat]
        ok = sum(1 for e, p in sub if e == p)
        if worst is None or ok / len(sub) < worst[1]:
            worst = (cat, ok / len(sub))
        print(f"  {cat:26s} {ok}/{len(sub)} exact")
    if worst:
        print(f"worst slice: {worst[0]} ({worst[1]:.3f})")
    # Negative control: flip the binary ground truth (CONFIRMED <-> NONE,
    # POTENTIAL excluded as an abstention class). A harness that still
    # passes under flipped labels is scoring something else.
    flipped = [(case, cur) for case, cur, _d in rows
               if case["expected"] in ("CONFIRMED", "NONE")]
    flipped_pass = sum(
        1 for case, cur in flipped
        if ("CONFIRMED" if cur == "CONFIRMED" else "NONE")
        == ("NONE" if case["expected"] == "CONFIRMED" else "CONFIRMED"))
    exact_pass = sum(1 for case, cur, _d in rows if cur == case["expected"])
    print()
    print(f"negative control: binary labels flipped on {len(flipped)} decided "
          f"cases; flipped exact-pass={flipped_pass}, original exact-pass="
          f"{exact_pass}/{len(rows)}. The flipped run must score strictly "
          "worse; a harness that cannot fail would tie or win.")
    print(f"exact-match misses (D-round4): "
          f"{sum(1 for case, cur, _d in rows if cur != case['expected'])}/{len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
