# Red team — Round 4 (epistemic calibration)

Method: each attack states the prediction made before running it, the
observed result, and the disposition. Attacks not executed are listed as
not run; nothing here is inferred from a test that does not exist.

| # | Attack | Prediction | Observed | Disposition |
|---|---|---|---|---|
| 1 | Generic TODO/FIXME marker in an unrelated module vs a FIXED claim | Pre-round-4 code confirms a false contradiction | After qualification: not confirmed; marker relevance is scoped to files the bound fix changed | FIXED. Regression: `tests/test_coroner_binding.py`, benchmark cases `unrelated-marker`, `commit-claim-unrelated-marker` |
| 2 | Spanish prose containing "todo" and identifiers containing "xxx" | Substring matching fabricates INCOMPLETE_PATCH | Strict whole-token markers only; claims stay SUPPORTED | FIXED earlier, re-verified: `tests/test_calibration.py` |
| 3 | Research document (EN/ES) disagreeing with an implementation claim | Whole-document disagreement confirms a contradiction | Document conflicts demoted to POTENTIAL at sentence level, requiring shared subject tokens | FIXED. KRAKADYL: 90 DOC_CONFLICT contradictions before; after qualification 17 POTENTIAL and no document-based CONFIRMED |
| 4 | Planned/proposed feature with an incomplete marker | A plan gets contradicted by current code | Modality gate: non-current modalities raise POTENTIAL only | FIXED. `tests/test_qualification_round4.py`; negative-control mutation (gate disabled) turns the test red, restored green |
| 5 | "The legacy parser was abandoned" in an actively maintained project | Project classified EXPLICITLY_ABANDONED | Feature-scoped declaration recorded under `scoped_declarations`; project stays ACTIVE | FIXED. Benchmark + regression tests |
| 6 | Negated ("not abandoned") and quoted (">") abandonment text | Word presence alone declares abandonment | Both excluded from project declarations with sentence-level checks | FIXED. `tests/test_qualification_round4.py` |
| 7 | Genuine project abandonment declaration in root README | Over-conservative health never fires | EXPLICITLY_ABANDONED with the exact declaration exposed | Verified: benchmark `health-explicit-project` |
| 8 | One marker reused against many claims (evidence fan-out) | Planner emits dozens of duplicate tasks; graph hides the reuse | Graph reports fan-out explicitly; planner groups contradicted claims by shared evidence and kind into one action | FIXED. `tests/test_workspace_health_graph.py`; KRAKADYL: 345 actions in 8 groups |
| 9 | Oversized source file | Memory blow-up or silent truncation | File is hashed, not text-indexed; skip counted in stats and warned | FIXED. `test_oversized_text_is_skipped_and_reported` |
| 10 | Cancellation during a 5000-commit excavation | Run cannot be stopped, or stops silently mid-state | Cooperative cancellation raises `ExcavationCancelled`; commit cap reports truncation | Partially fixed: cancellation is between phases, not inside one Git subprocess; no resume. Tested at API level |
| 11 | Filename with newline / hostile Git metadata | Name-status parsing mangles records | Parser hardened in Round 3 (`-z`, backwards file attribution re-verified this round after the single-pass rewrite broke it: 15 failures reproduced, fixed, suite green) | Verified by existing Round 3 adversarial suite |
| 12 | Branch/snapshot mismatch (uncommitted TODO under HEAD metadata) | Worktree bytes sealed under HEAD identity | Explicit `snapshot=head\|worktree` with divergence report (Round 2/3) | Verified: `tests/test_snapshot.py` |
| 13 | Hostile HTML/Markdown in repository text reaching the UI | Stored XSS through claim text | React escapes by construction; no raw-HTML rendering path exists in the frontend | Not re-run in a browser this round. Code-reviewed only; browser verification remains an open limitation |
| 14 | Partial index recovery after a killed excavation | Corrupt half-index presented as evidence | Not implemented: cancellation discards; no partial index is persisted or presented | Open limitation, stated in `docs/SCALE-BENCHMARK.md` |
| 15 | Prompt injection in README/commit text influencing hypotheses | Model output upgrades to facts | Hypotheses stay outside the seal with HYPOTHESIS provenance (Rounds 2-3); qualification adds no model path | Verified by existing provider/adversarial suites; no new model surface this round |

## Remaining exposures (not fixed, not hidden)

- The 3 (RAVEN-MEMORY) and 6 (KRAKADYL) CONFIRMED STILL_PRESENT items
  are unadjudicated; they may include true and false positives.
- Qualification can over-suppress: a true contradiction expressed with
  weak shared vocabulary degrades to POTENTIAL or UNVERIFIED. That is
  the accepted direction of error for this instrument.
- Browser-level rendering and interaction were not executed this round.
