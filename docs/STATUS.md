# Project status and inventory

Honest inventory of what exists, what does not, and what comes next.
Updated at the end of Round 4 (epistemic calibration round). Nothing in
the incomplete column is simulated or presented as working.

## Completed

| Capability | Evidence |
|------------|----------|
| Deterministic excavation, HEAD/worktree snapshots | `excavator.py`; snapshot and red-team suites |
| Claim archaeology with per-claim fix binding | `coroner.py`; binding, fixtures and Round 3 adversarial suites |
| Chronology, contradiction detection, resurrection planner | `chronos.py`, `planner.py` (risk, prerequisites, expected effect) |
| Sealed evidence core and tamper-evident ledger | `canonicalize.py`, `ledger.py`; determinism and chain tests, stdlib verifier `scripts/verify_bundle.py` |
| GitHub acquisition (bounded, credential-free) | `acquire.py`; parser rejection and controlled-runner tests |
| Persistent workspaces: save, reopen, staleness, compare, manifest, delete | `workspace.py`; roundtrip tests and API flow test |
| Health and abandonment indicators (never a bare score) | `health.py`; category and outside-seal tests |
| Typed evidence graph with speculative labeling | `graph.py`; consistency tests |
| MCP server, 9 read-only tools, no sampling | `mcp_server.py`; stdio contract and adversarial tests |
| Provider-neutral LLM: offline, OpenAI-compatible, Ollama | `llm.py`; adapter, malformed-output and fallback tests |
| Workbench frontend: launcher, overview, timeline, evidence, contradictions, hypotheses, plan, graph, health | `frontend/`; production build passes |
| Reports in JSON and Markdown with scope, method and reproduction | `export.py` |
| Threat model and limitations | `docs/THREAT_MODEL.md`, `docs/LIMITATIONS.md` |

Round 4 additions:

| Capability | Evidence |
|------------|----------|
| Qualified contradictions: CONFIRMED vs POTENTIAL, modality gate, file-scoped marker relevance, sentence-level document conflicts | `coroner.py`, `models.py`; `docs/EPISTEMIC-CALIBRATION.md` |
| Claim-to-evidence qualification: binding score (token overlap, never a probability), match basis, subject tokens exported in JSON/Markdown/UI | `export.py`, `frontend/`; link tests |
| Health: EXPLICITLY_ABANDONED only from a current root-README project declaration; negated/quoted/feature-scoped text excluded but visible | `health.py`; `tests/test_qualification_round4.py` |
| Versioned calibration benchmark with baselines, Wilson intervals, per-category slices and an inverted-label negative control | `benchmarks/round4/run_calibration.py` (case set `round4-calibration-v1`) |
| Single-pass streaming excavation with commit cap, text cap reporting, progress and cooperative cancellation; synthetic scale harness | `excavator.py`, `scripts/scale_benchmark.py`, `docs/SCALE-BENCHMARK.md` |
| Investigative graph: clusters by kind/subsystem/state, focus neighbourhoods, shared-evidence fan-out; analyst workflow Discover to Export; planner grouped by root cause and shared evidence | `graph.py`, `planner.py`, `frontend/` |

Round 5 additions:

| Capability | Evidence |
|------------|----------|
| Independent frozen evaluation set (16 cases, baselines A-D, three-way metrics with abstention) | `benchmarks/round5/`; pre-repair precision/recall 0.667/0.667, post-repair 1.000/0.667 (Wilson intervals in `docs/EPISTEMIC-CALIBRATION.md`) |
| Repairs: negated-claim agreement, platform scope demotion, STALE_HISTORY potentials, document antonym conflicts, STILL_PRESENT definition rule, REVERTED_FIX subject/hash tie | `coroner.py`; regression tests incl. mutation controls |
| VIGÍA stress test at 95e1251b (1,247 commits): 450 s, 215 MB RSS, 492 confirmed / 1,062 potential after repairs, health ACTIVE | `docs/SCALE-BENCHMARK.md` |
| Provisional adjudication artifact for RAVEN-MEMORY, KRAKADYL, VIGÍA samples | `benchmarks/round5/adjudication.md` |
| Browser verification: Playwright/Chromium, 18/18 workflow checks, screenshot inspected | `docs/REDTEAM-ROUND5.md` |
| Aggressive red team (Round 6): health quote/fence fabrication found and fixed; 12 vectors falsified | `docs/REDTEAM-ROUND6.md`, `health.py` |

Test baseline at this inventory: 90 backend tests passing, frontend
production build passing, browser workflow verified headless at
1280x900. Detector calibration against real mixed-language repositories
is recorded in `docs/CALIBRATION.md` and
`docs/EPISTEMIC-CALIBRATION.md`. Real-world precision remains
unmeasured; all real-repository labels are provisional.

## Incomplete (explicitly)

| Gap | Why it matters | Current honest state |
|-----|----------------|----------------------|
| GitHub API enrichment (issues, PRs, CI history) | Health analysis cannot see maintenance discussion | Not fetched; health says `STATUS_UNKNOWN` when evidence is missing |
| Trusted `VERIFIED` ingestion | No claim can currently exceed `SUPPORTED` from excavation alone | Requires a trusted test-execution evidence format; deliberately absent |
| Investigation cache | Large histories are re-excavated per API/MCP call | Correct but slow; stored reports mitigate reopening, not re-analysis |
| Browser-verified UI | The workbench was exercised over HTTP and build, not in a real browser | Visual and interaction behavior in a browser is unverified |
| Live GitHub acquisition test | Acquisition is tested with controlled runners, not the real network | Parser and limits are proven; real clone behavior is not |
| Graph scalability | Web drawing caps nodes and edges | Clusters, focus neighbourhoods and fan-out shipped in Round 4; the drawing still caps rendered nodes, with the full edge list and JSON export beside it |
| Held-out calibration | The Round 4 benchmark cases were spent during development | Validation only, n=10, Wilson intervals printed; no real-world accuracy claimed |
| Ground-truth adjudication of real repos | Remaining CONFIRMED items on RAVEN-MEMORY/KRAKADYL are unreviewed | Counts are observations; no precision claim made |
| Partial-index recovery | A cancelled excavation discards its work | Cooperative cancellation exists; resume does not |
| VIGÍA adjudication | 492 confirmed contradictions on VIGÍA are unadjudicated | Provisional labels only; independent human adjudication is the resolving experiment |
| Claim languages beyond English/Spanish | Other languages degrade to `UNVERIFIED` | Documented false negatives, preferred over fabrication |
| CI action pinning by digest | Supply-chain hardening for the workflow file | Actions are tag-pinned; digest pinning is open |
| Authenticated or remote API use | The API is loopback-only by design | No authority layer exists; do not expose it |

## Recommended next round (Round 5)

1. A held-out calibration set, built blind from real repositories and
   hand-adjudicated, so precision/recall stop being synthetic-only.
2. Run the scale harness against VIGÍA if it becomes available, and
   publish the measured numbers or the failure, whichever occurs.
3. Trusted verification-evidence ingestion so a real test run can
   upgrade a claim to `VERIFIED` with its own provenance chain.
4. Investigation caching keyed by HEAD plus snapshot scope, invalidated
   exactly when either changes; partial-index resume after cancellation.
5. Real-browser verification of the workbench, digest-pinned CI actions
   and a first tagged release.

The standing rule is unchanged: fewer levels, built correctly, over
broader simulation. A defensible UNKNOWN beats a fabricated
CONTRADICTION.
