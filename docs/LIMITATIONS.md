# Known limitations

Honest limits of the current level. A documented limitation is an asset;
an exaggerated capability is a defect.

- NECROMANCER never executes the target repository code or tests. For that
  reason `VERIFIED` is never issued from the presence of a token in a test
  file: token presence is a weak oracle. Trusted execution evidence is
  required to upgrade a claim, and no such ingestion exists yet.
- Claim extraction is pattern-based for English and Spanish completion,
  fix, verification and deprecation verbs. Other languages and indirect
  phrasing degrade to `UNVERIFIED` or `NOT_DETERMINABLE`, by design.
- `CONTRADICTED` requires positive evidence: an incomplete marker in the
  patched file, a revert touching the same files, a stub as the only
  implementation, or a document that denies another document. Many real
  false claims leave none of these traces and will read as `UNVERIFIED`.
- Since Round 4, every contradiction is qualified. Only CONFIRMED
  (same subject, scope and time; current or deprecated modality; bound
  positive evidence) changes a claim to `CONTRADICTED`. Document
  disagreement and non-current modalities are POTENTIAL review entries
  and change nothing. This deliberately trades recall for precision:
  true contradictions with weak shared vocabulary degrade to POTENTIAL
  or `UNVERIFIED`. The binding score on each link is token-overlap
  strength, not a probability. Calibration numbers come from a small
  synthetic benchmark spent during development
  (`benchmarks/round4/`); they are not real-world accuracy.
- Graph investigative views (clusters, focus, fan-out) are projections
  over the same typed edges. The fan-out threshold (>= 3 bindings) is a
  review heuristic, not a finding.
- Cancellation is cooperative between excavation phases and discards
  the run; there is no partial-index resume. See
  `docs/SCALE-BENCHMARK.md` for the measured synthetic harness, the
  VIGÍA stress test, and the explicit list of scale work not done.
- Round 5 measured the recall boundary explicitly: genuine
  contradictions expressed in different vocabulary, or as guarantees
  narrower in code than in documentation, are missed by construction
  (planted cases P4/P5 in `benchmarks/round5/`). The engine extracts
  those claims (VALIDATED/SANITIZED verbs) but cannot establish the
  contradiction without semantic or execution evidence, and does not
  fabricate it.
- Real-world precision and recall are unmeasured. All labels applied to
  real repositories so far are provisional machine-assisted
  adjudication by the system's own author, not independent human
  ground truth (`benchmarks/round5/adjudication.md`).
- The API CORS allowlist covers the documented loopback dev ports
  (5173/5174). Serving the frontend from any other origin yields a
  silently empty fixture list; use the documented ports.
- Browser verification was headless Chromium at 1280x900. Mobile
  viewports and screen-reader behavior were not exercised.
- History is read from the local clone as given. A shallow clone, a
  rewritten history, or work that only ever existed in an issue tracker
  is invisible here and is reported as missing evidence, never as proof
  that it did not happen.
- Model inference is optional and provider-neutral (offline templates,
  any OpenAI-compatible endpoint, or local Ollama). Without configuration
  the system stays in deterministic offline mode and says so. No model
  output is ever invented to fill the gap, and malformed model output is
  rejected instead of repaired into a plausible story.
- The MCP server and the HTTP API excavate on each call and return the
  full report; there is no investigation cache yet, so very large
  histories pay the excavation cost per tool call.
- Claim-to-fix binding is lexical: shared content tokens, changed paths,
  or claim origin. A fix described in completely different words than the
  claim will read as `UNVERIFIED` even when a human would link them.
  That false negative is preferred over a laundered false positive.
- File contents are indexed up to a size cap; very large artifacts are
  hashed but not text-searched, which can lower a claim to `UNVERIFIED`.
- GitHub acquisition is a bounded clone (depth 500, 200 MB). Older
  history is missing evidence by construction and the report says so.
  GitHub issues, pull requests and CI history are not fetched: health
  indicators use only what the clone contains, so `STATUS_UNKNOWN` is
  common and correct.
- Health indicators use the investigation wall-clock for recency and
  therefore live outside the seal; two investigations minutes apart can
  legitimately differ in `days_since_last_commit` on a boundary day.
- The web graph renders a bounded projection (first nodes and edges)
  with a full typed edge list beside it. Very large repositories need
  the list view or the JSON export, not the drawing.
- Snapshot comparison matches claims by deterministic claim id. A
  reworded claim appears as removed plus added, not as changed.
- Deleted branches and force-pushed history leave no local trace. The
  absence is reported as missing evidence, never reconstructed.
