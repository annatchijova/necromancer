# Round 4 calibration benchmark (v1)

Versioned, reproducible qualification benchmark:
`benchmarks/round4/run_calibration.py`
(case set `round4-calibration-v1`).

## Run

```bash
python benchmarks/round4/run_calibration.py
```

Builds tiny synthetic Git repositories with known ground truth, runs the
deterministic qualification pipeline (`excavator` + `coroner`, plus the
health classifier), and prints per-case results, the confusion counts for
the positive class, baselines, per-category slices and a negative control.

## The decision the metric serves

A CONFIRMED contradiction changes a claim to CONTRADICTED and feeds the
resurrection planner. A fabricated CONFIRMED is therefore the expensive
error, so precision is primary. A missed CONFIRMED stays visible as a
POTENTIAL conflict in the review queue, so recall is secondary but never
hidden. Binding scores are token-overlap strengths, not probabilities; no
calibration curve is reported because none is meaningful here.

## Cases and ground truth

| Case | Category | Expected | Ground truth |
|---|---|---|---|
| true-incomplete-fix | true_contradiction | CONFIRMED | FIXED claim; the bound fix leaves a strict marker in a file it changed |
| same-file-marker | true_contradiction | CONFIRMED | Commit claim; strict marker in a file that same commit changed |
| reverted-fix | regression | CONFIRMED | Fix later reverted; defect present again at HEAD |
| unrelated-marker | false_contradiction | not confirmed | Marker lives in a module the fix never touched |
| commit-claim-unrelated-marker | false_contradiction | not confirmed | Marker only in an untouched module |
| planned-vs-marker | modality_mismatch | not confirmed | A planned feature with a marker is a plan, not a broken promise (raised as POTENTIAL) |
| health-feature-abandoned | abandonment_scope | not abandoned | A named legacy component was abandoned; the project was not |
| health-negated | abandonment_negation | not abandoned | Negated sentence states the opposite |
| health-quoted | abandonment_quotation | not abandoned | Quoted external text is not a project declaration |
| health-explicit-project | abandonment_explicit | abandoned | Root README declares the project itself abandoned |

## Baselines (claims cases only)

Reported beside the system, always:

- never-confirm and always-confirm (constant classifiers),
- naive-substring: the pre-qualification rule (any TODO/FIXME/XXX
  substring anywhere confirms). It is the regression this round removed.

## Negative control

Ground-truth labels are inverted and the harness must fail. If it still
passed, it would be scoring something other than these cases.

## Honesty limits

The cases were inspected during development: this is a validation set
spent during tuning, not a held-out test set. n=10 is far too small for
generalization, which is why a Wilson 95% interval is printed next to
precision and recall. Synthetic ground truth cannot represent real
repository ambiguity, selection bias toward already-known failure modes,
or distribution shift to real histories. Do not quote these numbers as
universal accuracy. See `docs/EPISTEMIC-CALIBRATION.md`.
