# Red team — Round 5 (adversarial epistemic validation)

Method: predictions were recorded before each run where the run was
designed as a test; where a defect was found by accident (VIGÍA), the
table says so. Nothing here is inferred from a test that does not exist.

| # | Attack / probe | Prediction | Observed | Disposition |
|---|---|---|---|---|
| 1 | Fresh evaluation set (16 cases frozen before evaluation) against the Round 4 system | Round 4 precision would drop below its development-set 1.000 if H5 (leakage) held | Precision 0.667, recall 0.667, exact 10/16 | H5 supported in part. Set kept frozen; repairs evaluated against the same hash `02cb197ba7616316` |
| 2 | Negated claim "the export feature is not implemented yet" + its own stub | Engine would read the stub as contradiction (STUB_ONLY) | CONFIRMED contradiction of a true sentence | FIXED: negated claims agree with their stubs. Regression `test_negated_claim_agrees_with_its_stub` |
| 3 | FIXED claim scoped "on Linux", marker in `win_paths.py` changed by the same commit | File-scope rule would confirm across platforms | CONFIRMED (INCOMPLETE_PATCH) | FIXED: platform scope mismatch demotes to POTENTIAL. Regression `test_cross_platform_marker_is_potential_not_confirmed` |
| 4 | Historical claim true in v1; marker added later to the same file | Modality gate would swallow it entirely | Nothing raised (UNVERIFIED, silent) | FIXED: STALE_HISTORY raises POTENTIAL. Regression `test_historical_claim_with_marker_is_potential` |
| 5 | "exporter is implemented and complete" vs "exporter remains incomplete" in another document | Two-shared-token rule might never fire | Nothing raised | FIXED: polarity antonym + 1 shared subject token raises POTENTIAL. Regression `test_doc_antonym_conflict_is_potential` |
| 6 | Narrative prose containing "removed" (aviation history in a research document) vs demo code | STILL_PRESENT might confirm on generic token overlap | CONFIRMED on KRAKADYL (5 of its 6 confirmed) | FIXED: CONFIRMED requires the identifier to be DEFINED in code; mention is POTENTIAL. Provisional adjudication in `benchmarks/round5/adjudication.md` |
| 7 | VIGÍA: 3 real revert commits, one restoring hundreds of bundle files | File-overlap revert binding would fan out | 683 REVERTED_FIX confirmations from 3 reverts | FIXED: confirmation requires the revert to quote the fix subject or cite its hash; file-only overlap is POTENTIAL. Regression `test_file_only_revert_overlap_is_potential` |
| 8 | New verb patterns (VALIDATED/SANITIZED) stealing DEPRECATED claims via `sanitize_html` | Precedence risk noted before running the full suite | P2 broke exactly that way (verb became SANITIZED) | FIXED by narrowing the pattern (`sanitized|sanitizes`, no stem match). Regression `test_deprecated_wins_over_sanitize_substring` |
| 9 | Planted genuine contradictions in different vocabulary / narrower scope (P4, P5) | Lexical engine would miss at least one | Missed both; claims now extracted (VALIDATED/SANITIZED verbs) but state stays UNVERIFIED/SUPPORTED | NOT FIXED. Recorded false negatives. Establishing them needs semantic or execution evidence the engine deliberately does not fabricate |
| 10 | Hostile fixture: prompt-injection README, invalid UTF-8, binary blob, 1 MB single line, secret-bearing files, symlink escaping the repo | Excavation must treat content as data, stay bounded, never execute or obey | No VERIFIED issued; symlink target content never indexed; oversized file skipped and reported; secrets never enter hypotheses | FIXED/VERIFIED: `tests/test_security_round5.py` |
| 11 | Browser workflow (Playwright/Chromium, real API + dev server) | At least one integration defect expected | 18/18 checks pass after fixing the test flow; one real finding: preview origins outside the CORS allowlist (5173/5174) silently get an empty fixture list | PARTIAL: CORS allowlist unchanged by design (loopback dev ports documented); recorded as a usability limitation. Screenshot inspected manually |
| 12 | Mutation control on the modality gate and revert rule | Removing each gate must turn its regression red | Both mutations observed red and restored green: modality gate (Round 4), revert subject/hash tie (`test_file_only_revert_overlap_is_potential` fails when any file overlap confirms) | VERIFIED |
| 13 | Partial excavation presented as complete | Checkpoint/resume does not exist; cancellation discards | Confirmed absent by design | DEFERRED with a written design (`docs/SCALE-BENCHMARK.md`). A partial result is never presented as an investigation |

## Remaining exposures (not fixed, not hidden)

- Real-world precision/recall remain unmeasured. Every real-repository
  label in this project is provisional machine-assisted adjudication.
- 492 CONFIRMED on VIGÍA are unadjudicated; the sampled eight are
  UNRESOLVED. They may contain many true incomplete fixes from the
  project's own audit history and an unknown number of vocabulary
  bindings.
- Recall is bounded by vocabulary: guarantees violated in scope or
  wording (P4/P5) are missed by construction.
- The browser was verified headless at one viewport (1280x900);
  responsive/mobile layouts and screen-reader behavior were not
  exercised.
