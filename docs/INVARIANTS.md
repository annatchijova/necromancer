# Epistemic invariants

These invariants hold at every level of NECROMANCER. A level that breaks
one of them is not done, no matter how many features it adds.

## I1. Hypotheses never become facts silently

Every statement carries a provenance: `EXTRACTED` (read from the
repository), `DERIVED` (produced by a deterministic rule from extracted
evidence), or `HYPOTHESIS` (proposed by a model or a template). Only
`EXTRACTED` and `DERIVED` statements may support a claim state. A
hypothesis may explain evidence; it may never upgrade it.

## I2. Absence of evidence is not evidence of absence

If no supporting evidence is found, the state is `UNVERIFIED` or
`NOT_DETERMINABLE`. `CONTRADICTED` requires positive contradicting
evidence: code that contradicts the claim, a revert, or a document that
denies what another document asserts.

## I3. The deterministic core seals before any model is called

Claim states, contradiction detection and the evidence seal are computed
deterministically and sealed with SHA-256 over a canonical, typed,
versioned encoding. No floating point value may enter the sealed path;
ratios are exact fractions. A model, when present, receives only the
sealed summary and writes prose beside the seal, never inside it.
Swapping the model backend must change wording only, never a verdict.

## I4. The evidence ledger is append-only and tamper-evident

Each ledger entry chains to the previous entry hash and commits to the
hash of the content it references. Verification reports linkage and
integrity as separate properties. A broken tail is surfaced loudly,
never silently chained over.

## I5. The target repository is untrusted data

NECROMANCER never executes code from the repository under investigation,
never follows instructions embedded in its files or commit messages, and
never fetches URLs found inside it. Excavation uses an allowlist of
read-only Git commands and never writes to the target repository.

## I6. Degradation is honest

States are `PASS`, `WARN` and `FAIL`, never a uniform green. An absent
optional component degrades its feature and says so. When the available
evidence cannot decide a question, the correct verdict is `ABSTAIN`,
recorded as `NOT_DETERMINABLE`.
