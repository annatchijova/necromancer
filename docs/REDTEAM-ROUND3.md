# Security Audit — NECROMANCER
## Red Team Round 3

**Date:** 2026-11-03  **Method:** Abductive Engineering (A-D-I) + Red-Team Auditing
**Scope:** Excavator, Coroner binding, LLM providers, MCP server, frontend rendering
**Base:** `main` @ `bad749f` (fixes in this round are uncommitted, pending review)
**Reproducible evidence:** [tests/test_redteam.py](../tests/test_redteam.py)

## Threat model

- Attacker CAN: fully craft the target repository (files, filenames,
  `.gitattributes`, local Git config), control a configured model
  endpoint and its responses, and supply very large inputs. The attacker
  can call the MCP and HTTP surfaces as a local client.
- Attacker CANNOT: modify NECROMANCER code, exceed the invoking user's
  filesystem privileges, or reach tools outside the read-only allowlist.

## Epistemic legend

CODE FACT · PLAUSIBLE HYPOTHESIS · CONFIRMED BY INDUCTION · FALSIFIED

## Executive summary

| ID | Severity | Level | Module | Finding |
|----|----------|-------|--------|---------|
| RT3-01 | Low | CONFIRMED BY INDUCTION, fixed | Excavator | Hostile filenames were mangled before hashing |
| RT3-02 | Low | CONFIRMED BY INDUCTION, fixed | LLM providers | Model output could flood a report without caps |
| RT3-03 | Hygiene | CODE FACT, hardened | Excavator | Whole blobs were loaded into memory to hash them |

## Findings

### RT3-01 — Newline in a filename corrupted the artifact inventory

**Severity:** Low  **Epistemic level:** CONFIRMED BY INDUCTION  **Bucket:** vulnerability

- **Surprise:** a committed file named with an embedded newline must
  appear in the inventory under its exact name, or evidence can silently
  vanish from claim analysis.
- **Prediction, stated before the fix:** `excavate` will not list the
  exact path. **Observed:** the path was mangled by line-based `ls-tree`
  parsing and the file was skipped. After switching the tree listing to
  `-z`, the exact path is listed and hashed.
- **Causal chain:** line-split parsing, Git quoting, mangled path, failed
  blob lookup, file absent from texts, claims about it degrade silently.
- **Fix:** `ls-tree -z`. Regression test:
  `test_newline_in_filename_keeps_exact_path`.

### RT3-02 — A hostile or broken model endpoint could flood hypotheses

**Severity:** Low  **Epistemic level:** CONFIRMED BY INDUCTION  **Bucket:** vulnerability

- **Prediction:** a response with 500 hypotheses is accepted whole.
  **Observed:** 500 accepted. After the fix, output is capped at 50
  hypotheses, statements at 500 characters, discriminators at 5 per
  hypothesis. Content remains `HYPOTHESIS` either way, so no verdict
  could move; the risk was report flooding, not authority.
- **Regression test:** `test_model_output_is_capped`.

### RT3-03 — Whole-blob reads for hashing

**Severity:** Hygiene  **Epistemic level:** CODE FACT  **Bucket:** hygiene

- Hashing read each blob fully into memory (`read_bytes`,
  `git show` capture). A very large tracked blob could exhaust memory
  during a read-only investigation.
- **Hardening:** blobs are now streamed in 1 MiB chunks for both HEAD
  (`git cat-file`) and worktree scopes; text is retained only up to the
  existing cap. Correctness on a multi-megabyte blob is covered by
  `test_large_blob_is_hashed_but_not_text_indexed`. Peak-memory figures
  were not benchmarked, so no quantitative claim is made.

## Discarded (non-exploitable) vectors

| Vector | Result | Why it failed |
|--------|--------|---------------|
| Git filter/textconv driver execution via hostile repo config | FALSIFIED | Excavation never checks out and never diffs content; the canary driver never ran in either snapshot scope (`test_git_filter_driver_is_never_executed`) |
| Seal instability under `PYTHONHASHSEED` variation | FALSIFIED | Two processes with different hash seeds produced the identical seal (`test_seal_is_stable_across_hash_seeds`) |
| Prompt injection in README reaching a verdict | FALSIFIED | Deterministic policy decides; injected text stays claim data and never yields `VERIFIED` (contract and adversarial suites) |
| Stored XSS through claim text in the frontend | FALSIFIED | Claim text renders through React escaping; no raw-HTML surface exists in the frontend source |
| MCP tools reading arbitrary local repositories | Threat-model assumption | The MCP client is the local principal; read access to local repos is the product. There is no network listener and no write tool to abuse |
| Synonym-only fix descriptions evading claim binding | PLAUSIBLE HYPOTHESIS | Accepted and documented in `docs/LIMITATIONS.md`: a lexical false negative (`UNVERIFIED`) is preferred over a laundered false positive |

## Residual risk, stated plainly

- Excavation still spawns one `git show` per commit (bounded at 5,000
  commits). A hostile history is slow, not dangerous, for a local client.
- The HTTP API is unauthenticated and intended for localhost use only.
  Do not expose it beyond loopback without adding an authority layer.
- The hash chain proves insertion order and integrity of the ledger,
  not that the recorded history is semantically true. A wrong verdict
  can be sealed; sealing has never claimed otherwise.
