# Detector calibration

How the contradiction detector is kept able to be wrong in the open.

## Baseline incident (Round 3, real repository)

On the first real-repository investigation (107 commits, mixed English
and Spanish), the detector reported 83 `SUPPORTED` and 52 `CONTRADICTED`
claims. Breakdown of the contradictions: 40 `INCOMPLETE_PATCH`,
9 `DOC_CONFLICT`, 3 `STILL_PRESENT`.

Hand audit of the two dominant evidence files showed strict
code-convention markers (`TODO`, `FIXME`, `XXX` as whole tokens, or
`NotImplementedError`) equal to **zero** in both. The old rule matched
substrings on lowered text, so it fired on:

- the Spanish word `todo` inside a data list, and
- `xxx` inside an ordinary identifier.

Those 40 contradictions were false positives by construction: positive
evidence manufactured from spelling, in violation of the rule that
`CONTRADICTED` requires real contradicting evidence.

## Fix

Incomplete markers are now matched case-sensitively as whole tokens:
`\b(TODO|FIXME|XXX)\b|NotImplementedError`. The same strict count feeds
health indicators. Prose discussing incompleteness no longer counts.

Negative and positive controls live in `tests/test_calibration.py`:
Spanish `todo` prose does not contradict, `xxx` inside an identifier
does not contradict, and a real `TODO:` in a patched file still does.

## After measurement (same repository, same day)

| | Before | After |
|--|--------|-------|
| SUPPORTED | 83 | 123 |
| CONTRADICTED | 52 | 12 |
| INCOMPLETE_PATCH | 40 | 0 |

The remaining 12 (9 `DOC_CONFLICT`, 3 `STILL_PRESENT`) were not audited
to ground truth here; they are reported as detector output, not as
adjudicated facts. This repository has no labeled ground truth, so no
precision figure is claimed: what is claimed is narrower and earned —
every removed contradiction lacked a strict marker, and every control
in the suite behaves as required in both directions.

## Standing rule

Any future marker or pattern change must ship with: one negative control
that previously fired, one positive control that must still fire, and a
before/after count on at least one real, mixed-language repository.

## Round 4 continuation

Marker strictness was necessary but not sufficient: the association
itself was unqualified. Round 4 qualifies every contradiction
(CONFIRMED vs POTENTIAL), adds the modality gate and file-scoped marker
relevance, and measures the result in
`docs/EPISTEMIC-CALIBRATION.md` with the versioned benchmark in
`benchmarks/round4/`. The 9 DOC_CONFLICT items above are POTENTIAL
review entries under the new rules; the 3 STILL_PRESENT remain
CONFIRMED and unadjudicated.
