# Architecture

NECROMANCER is an evidence engine. Language models are interchangeable
investigators, never epistemic authorities.

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
