# Architecture

NECROMANCER is an evidence engine. Language models are interchangeable
investigators, never epistemic authorities.

See also: [THREAT_MODEL.md](THREAT_MODEL.md) for trust boundaries and
[STATUS.md](STATUS.md) for the completed/incomplete inventory.

```mermaid
flowchart TB
    subgraph untrusted["Untrusted data — never instructions"]
        repo["Target repository<br/>commits · docs · tests · branches"]
    end

    subgraph core["Deterministic core — sealed before any model exists"]
        excavator["Excavator<br/>read-only Git allowlist<br/>snapshot: HEAD or worktree"]
        chronos["Chronos<br/>provenance-linked timeline"]
        coroner["Coroner<br/>claims bound to specific evidence"]
        seal["SHA-256 seal<br/>canonical · typed · no floats"]
        ledger["Evidence Ledger<br/>append-only hash chain"]
        excavator --> chronos --> coroner --> seal --> ledger
    end

    subgraph interp["Interpretation — outside the seal, always HYPOTHESIS"]
        offline["Offline templates"]
        openai["OpenAI-compatible API"]
        ollama["Local Ollama"]
        planner["Resurrection Planner<br/>reversible steps only"]
    end

    subgraph surfaces["Read-only surfaces"]
        cli["CLI"]
        api["FastAPI"]
        mcp["MCP server<br/>external clients reason themselves"]
        web["React interface"]
    end

    repo --> excavator
    seal -.->|sealed summary only| offline
    seal -.->|sealed summary only| openai
    seal -.->|sealed summary only| ollama
    coroner --> planner
    core --> surfaces
    interp --> surfaces
    surfaces --> investigator["Human or external model<br/>receives evidence + labeled hypotheses"]
```

## Workbench layers added in Round 3

- **Acquisition** (`acquire.py`): only `https://github.com/<owner>/<repo>`
  is accepted, cloned bounded (depth 500, 200 MB, no checkout, no
  submodules, no credentials) into an isolated workspace. Acquisition
  failures are errors, never findings, and the footprint is recorded.
- **Persistence** (`workspace.py`): SQLite investigation store keyed by
  seal. Reopening never rewrites stored evidence; a changed HEAD reports
  `STALE`. Snapshots can be compared at claim level and exported as a
  manifest.
- **Health** (`health.py`): observable indicators (recency, branches,
  TODO/FIXME, tests, CI config, tags, explicit maintenance statements)
  with a category that inactivity alone can never raise to abandoned.
- **Evidence graph** (`graph.py`): typed projection (`SUPPORTED_BY`,
  `CONTRADICTED_BY`, `INTRODUCED_IN`, `MODIFIED_IN`, `REFERENCES`,
  `HYPOTHESIZED_CAUSE`, `REQUIRES_VERIFICATION`). Speculative edges are
  labeled; the graph is never the source of truth.
- **Verification bundle** (`scripts/verify_bundle.py`): stdlib-only
  checker for report provenance and ledger chain integrity, independent
  of the producing code.

Rules that the diagram encodes:

- The target repository is data. Its files and commit messages are never
  executed and never treated as instructions.
- Claim states are computed deterministically and sealed. A provider may
  only add `HYPOTHESIS` rows beside the seal; swapping providers changes
  wording, never a verdict.
- The MCP server exposes the same deterministic evidence to external
  clients so they can reason themselves. It calls no model and uses no
  sampling.
- Every surface is read-only with respect to the target repository.
