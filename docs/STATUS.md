# Project status and inventory

Honest inventory of what exists, what does not, and what comes next.
Updated at the end of Round 3 (workbench round). Nothing in the
incomplete column is simulated or presented as working.

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

Test baseline at this inventory: 68 backend tests passing, frontend
production build passing, demo exercised end-to-end over the real HTTP
API with synthetic fixtures.

## Incomplete (explicitly)

| Gap | Why it matters | Current honest state |
|-----|----------------|----------------------|
| GitHub API enrichment (issues, PRs, CI history) | Health analysis cannot see maintenance discussion | Not fetched; health says `STATUS_UNKNOWN` when evidence is missing |
| Trusted `VERIFIED` ingestion | No claim can currently exceed `SUPPORTED` from excavation alone | Requires a trusted test-execution evidence format; deliberately absent |
| Investigation cache | Large histories are re-excavated per API/MCP call | Correct but slow; stored reports mitigate reopening, not re-analysis |
| Browser-verified UI | The workbench was exercised over HTTP and build, not in a real browser | Visual and interaction behavior in a browser is unverified |
| Live GitHub acquisition test | Acquisition is tested with controlled runners, not the real network | Parser and limits are proven; real clone behavior is not |
| Graph scalability | Web drawing caps nodes and edges | Full edge list and JSON export carry the complete projection |
| Claim languages beyond English/Spanish | Other languages degrade to `UNVERIFIED` | Documented false negatives, preferred over fabrication |
| CI action pinning by digest | Supply-chain hardening for the workflow file | Actions are tag-pinned; digest pinning is open |
| Authenticated or remote API use | The API is loopback-only by design | No authority layer exists; do not expose it |

## Recommended next round (Round 4)

1. Optional, credentialed-by-the-operator GitHub enrichment behind the
   same acquisition boundary, feeding health indicators without touching
   offline determinism.
2. A trusted verification-evidence format so a real test run can upgrade
   a claim to `VERIFIED` with its own provenance chain.
3. Investigation caching keyed by HEAD plus snapshot scope, invalidated
   exactly when either changes.
4. Real-browser verification of the workbench against the demo API.
5. Digest-pinned CI actions and a first tagged release.

Round 4 should keep the same rule as every round so far: fewer levels,
built correctly, over broader simulation.
