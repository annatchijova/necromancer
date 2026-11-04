# Epistemic calibration (Round 4)

How NECROMANCER decides that two pieces of evidence genuinely conflict,
and how it now refuses to decide when they do not.

## The failure this round fixed

On real repositories investigated before this round, generic incomplete
markers contradicted unrelated claims:

- RAVEN-MEMORY (107 commits observed): 83 SUPPORTED / 52 CONTRADICTED,
  dominated by markers in `memory_engine.py` and `api_server.py`.
- KRAKADYL (226 commits observed): 449 SUPPORTED / 164 CONTRADICTED /
  50 UNVERIFIED, `EXPLICITLY_ABANDONED` despite recent activity, and 90
  document conflicts, mostly against a bilingual research report.

Those counts were UI observations, not ground truth. The defect class:
an unqualified association (any marker, anywhere, against any claim) was
presented as a contradiction. Round 4 rebuilds the association as a
qualification decision with explicit dimensions, and demotes everything
that is not a defensible incompatibility to POTENTIAL.

## Qualification dimensions

Every contradiction now carries a qualification:

- CONFIRMED: same subject, compatible scope and time, current modality,
  and positive contradicting evidence bound to the claim. Only CONFIRMED
  changes a claim to CONTRADICTED.
- POTENTIAL: a conflict worth human review that changes no state:
  document-vs-document or document-vs-code disagreement at sentence
  level, non-current modality, or any association whose subject, scope
  or time cannot be aligned defensibly.

Dimensions applied, in order: subject identity (shared subject tokens),
predicate/verb, scope and subsystem (the bound commit must have changed
a relevant file), temporal applicability (reverts and history), modality
(CURRENT and DEPRECATED can be contradicted; PLANNED, PROPOSED and
HISTORICAL can only raise POTENTIAL), negation and polarity, and marker
relevance scoped to the files the bound fix itself changed. A generic
TODO/FIXME marker in an unrelated module can no longer contradict a fix.

## Claim-to-evidence qualification

Each link records: exact source location (`origin`, line), the claim
extraction rule, relationship type, why it exists (`rationale`), the
match basis (origin, message, path, document, code), shared subject
tokens, and a binding score. The binding score is token-overlap strength.
It is not a calibrated probability and is never presented as one, in the
API, the exports or the UI.

## Health classification

`EXPLICITLY_ABANDONED` now requires a current, attributable,
project-scoped declaration in the root README. Negated sentences ("not
to be abandoned"), quoted material, feature/component-scoped sentences
and research documents are excluded; feature-scoped declarations remain
visible as `scoped_declarations` instead of being silently dropped.
Ambiguity resolves to UNKNOWN/ACTIVE by recency evidence, never to
abandoned-by-inactivity. Recent commits do not prove maintenance and old
commits do not prove abandonment; the category always exposes its exact
supporting evidence (`declarations`, `category_evidence`).

## Re-measurement after qualification

Live repositories keep changing, so these are dated snapshot
observations, not ground truth and not accuracy claims. Measured with
`investigate()` on 2026-11-03 in this workspace:

| Repository | SUPPORTED | CONTRADICTED (CONFIRMED) | POTENTIAL | Health |
|---|---|---|---|---|
| RAVEN-MEMORY | 132 | 3 (STILL_PRESENT) | 0 | ACTIVE |
| KRAKADYL | 601 | 6 (STILL_PRESENT) | 17 | ACTIVE |

The remaining CONFIRMED items are deprecations whose token is still
present in current code. They have not been hand-adjudicated to ground
truth; no precision claim is made about them. The swing risk is stated
plainly: qualification may also suppress true contradictions (false
negatives). The benchmark measures both directions on labeled synthetic
cases; real repositories remain unadjudicated.

## Calibration benchmark

`benchmarks/round4/run_calibration.py` (case set
`round4-calibration-v1`, n=10 labeled cases). Decision-matched metrics:
precision is primary because CONFIRMED feeds the planner; recall is
secondary because misses remain visible as POTENTIAL.

Observed on this machine: tp=4 fp=0 tn=6 fn=0; precision 1.000 with
Wilson 95% interval 0.510-1.000; recall 1.000 (same interval). The
interval is the honest part of that sentence: n is tiny.

Baselines on the claim cases: never-confirm precision 1.000 / recall
0.000; always-confirm precision 0.500 / recall 1.000; the pre-qualification
naive-substring rule precision 0.400 / recall 0.667 / FPR 1.000 — the
regression this round removed, kept measurable.

Negative control: inverted ground-truth labels fail 10/10 cases, which
proves the harness can produce a bad score. The labeled set was spent
during development (validation, not held-out test). No universal
accuracy is claimed.

## Round 5: independent evaluation and what it found

Round 4's benchmark was spent during development, so Round 5 built a
new frozen set (`benchmarks/round5/`, case set hash `02cb197ba7616316`,
16 cases, labels from fixture construction by the same agent — not
independent human ground truth) and evaluated four systems on it.

Pre-repair Round 4 system on the new set: precision 0.667 (Wilson
0.300–0.903, n=6), recall 0.667 (n=6), exact match 10/16. The Round 4
development-set score of 1.000 did not generalize: hypothesis H5
(calibration leakage) is supported as a partial explanation, and H4
(mixed effect) is the overall verdict — specificity genuinely improved
in the categories Round 4 targeted, while new failure modes sat
outside them.

Defects found by the new set and by VIGÍA, all fixed with regression
tests (details in `docs/REDTEAM-ROUND5.md`):

1. Negated claims ("not implemented yet") were contradicted by their
   own stub (STUB_ONLY). A negated claim now agrees with its stub.
2. Cross-platform markers confirmed contradictions; platform scope
   mismatch now demotes to POTENTIAL.
3. Historical claims raised nothing when their file later gained a
   marker; they now raise POTENTIAL (STALE_HISTORY).
4. Document antonym conflicts ("complete" vs "incomplete") needed two
   shared tokens and fired never; polarity opposition with one shared
   subject token now raises POTENTIAL.
5. STILL_PRESENT confirmed narrative prose containing "removed" (an
   airplane story in KRAKADYL research). CONFIRMED now requires the
   deprecated identifier to be DEFINED in code; mention is POTENTIAL.
6. REVERTED_FIX confirmed on file overlap alone: 3 revert commits in
   VIGÍA produced 683 confirmations. Confirmation now requires the
   revert to quote the fix subject or cite its hash.
7. A verb-precedence regression (SANITIZED stealing DEPRECATED claims
   on `sanitize_html`) was caught by the evaluation and fixed.

Post-repair on the same frozen set: precision 1.000 (Wilson 0.510–1.000,
n=4 confirms), recall 0.667 (0.300–0.903, n=6), abstention 0.250,
exact match 14/16. The two remaining misses are planted genuine
contradictions the lexical engine cannot establish — a guarantee
narrower in implementation than in documentation, and a stub described
in different vocabulary. They are recorded as false negatives, not
relabelled. Answering the round's central question: Round 4 genuinely
reduced false positives (H1 holds for marker, modality, documentation
and abandonment categories), AND introduced/masked false negatives and
fan-out defects that only the new set and VIGÍA exposed (H2/H4). H3
also contributed: real-repo populations moved between rounds because
revisions and claim extraction changed, so cross-round count
comparisons are not accuracy measurements.

Real-repository effect of the Round 5 repairs at recorded revisions:
RAVEN-MEMORY @028aa4d2 confirmed 3 → 0 (one demoted case is a leaning-
true contradiction; the recall cost is recorded in the adjudication
artifact). KRAKADYL @4d319251 confirmed 6 → 1 (the survivor is
UNRESOLVED). VIGÍA @95e1251b confirmed 1,098 → 492 with POTENTIAL
249 → 1,062. Provisional machine-assisted adjudication:
`benchmarks/round5/adjudication.md`. Real-world precision is still
unmeasured; no number in this section claims it.

A note on INCOMPLETE_PATCH semantics, stated once and plainly: a
CONFIRMED incomplete patch means the bound fix's own files still carry
an explicit incomplete marker. It does not demonstrate that the
original defect is exploitable or even present; the marker is the
fix author's own unfinished-work signal, in the fix's own scope.

## Invariant preserved

Qualification, health and the graph are derived after the evidence seal
is computed (`cli.investigate` seals before hypotheses, planner, health
and graph). Two investigations of the same snapshot produce the same
seal; the seal covers claims, links and contradictions with their
qualification-relevant state, never timestamps.
