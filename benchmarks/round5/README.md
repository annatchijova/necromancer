# Round 5 evaluation dataset (v1)

Independent-of-Round-4 evaluation fixtures, constructed and frozen
before evaluation: `benchmarks/round5/cases.py` defines each case, its
expected three-way label (CONFIRMED / POTENTIAL / NONE) and the
ground-truth rationale from construction. `run_evaluation.py` hashes
the case definitions (`case_set_sha256`) into every run; editing a case
changes the hash and invalidates comparisons with earlier runs.

## Run

```bash
python benchmarks/round5/run_evaluation.py
```

## Partitions and provenance

- Partition: `evaluation-new` (16 cases). No case paraphrases a Round 4
  calibration case; two categories (narrower implementation, different
  vocabulary) were planted specifically as expected false negatives.
- Label provenance: same-agent construction. The agent planted each
  fixture and labeled it from what was planted. This is NOT independent
  human adjudication, and the set must never be described as externally
  validated ground truth.
- Ambiguous cases are labeled POTENTIAL and stay ambiguous. They are
  not forced into true/false.
- Development/calibration sets from Round 4 remain separate
  (`benchmarks/round4/`); nothing here reuses them.

## Systems compared on the same frozen cases

- A: never confirm. B: always confirm (where a target claim exists).
- C: naive-substring reconstruction of the pre-qualification rule
  (approximation at claim level, labeled as a reconstruction).
- D: current NECROMANCER (working tree; pre-repair Round 5 numbers are
  recorded in `docs/EPISTEMIC-CALIBRATION.md`).

## Metrics

Three-way confusion matrix; binary metrics under the documented mapping
CONFIRMED vs {POTENTIAL, NONE}; coverage and abstention (POTENTIAL is
the abstention); selective precision/recall on decided cases; Wilson
95% intervals with denominators; per-category exact-match slices; a
label-flip negative control that must score strictly worse.

Real-world observations and their provisional adjudication live in
`benchmarks/round5/adjudication.md`.
