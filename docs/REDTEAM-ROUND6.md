# Red team — Round 6 (aggressive)

Date: 2026-11-03. Method: A–D–I with predictions stated before runs.
Threat model: the attacker controls the investigated repository's
contents, filenames, commit messages and metadata, and can call the
local API/MCP surfaces. The attacker cannot modify NECROMANCER, holds
no credentials, and cannot execute code on the host except through
NECROMANCER's own read-only Git subprocesses. Probes ran from
`/tmp/redteam6.py` and `/tmp/redteam6b.py` (scratch, reproducible from
this document's fixtures).

Epistemic legend: CODE FACT / PLAUSIBLE HYPOTHESIS /
CONFIRMED BY INDUCTION / FALSIFIED.

## Findings

### RT6-1 — Fenced and quoted README text classified health categories
Severity: medium (fabricated EXPLICITLY_ABANDONED / SUPERSEDED).
Level: CONFIRMED BY INDUCTION. Bucket: software vulnerability (in the
epistemic sense this project defends: a fabricated verdict).

Prediction: a README that merely shows an example announcement inside
a code fence or a blockquote would still feed the health categories,
because only the abandonment-declaration scan skipped `>` lines and
the superseded/archived checks matched raw root text.

Observed: fixture with `> This repository has been archived.` plus a
fenced `This project is abandoned.` classified EXPLICITLY_ABANDONED;
a quoted "superseded by" example classified SUPERSEDED.

Causal chain: root README lines → unfiltered `root_text` → phrase
match → category, with the quote/fence context discarded.

Fix: one eligibility filter (quotes and fenced blocks excluded) now
feeds the declaration scan and every category phrase check
(`health.py`). Regression:
`test_fenced_and_quoted_health_phrases_are_not_declarations`.
All 9 probes pass after the fix; the genuine declaration case
(`health-explicit-project`, suite test) still fires.

## Falsified vectors (tried, could not exploit)

| Vector | Result | Why it failed |
|---|---|---|
| Git argument injection via a repo path beginning with `--upload-pack=...` | FALSIFIED | Paths resolve to directories first; subprocess uses argv lists, no shell |
| Empty repository (no commits) as a crash/500 vector | FALSIFIED | Clean `ExcavationError` (no HEAD), API maps it to 400 |
| Monotonicity attack: adding unrelated TODO/FIXME documents after a claim is SUPPORTED | FALSIFIED | Claim state unchanged (SUPPORTED → SUPPORTED); file-scoped marker relevance holds |
| Future/odd commit dates crashing health | FALSIFIED | Category resolves to ACTIVE with the oddity visible in evidence |
| Unicode, emoji and curly-quote claim text | FALSIFIED | Extracted normally, no crash, no promotion |
| Markdown structure injection via claim text ("## Hypotheses", pipes) | FALSIFIED | Export cell escaping flattens newlines/pipes; exactly one real Hypotheses header in output |
| Canonical collisions (1 vs "1" vs true vs [1]) | FALSIFIED | Typed canonical forms are pairwise distinct; seal is SHA-256 over them |
| Bundle tampering (claim state edited to VERIFIED post-hoc) | FALSIFIED | Independent stdlib verifier rejects the bundle (exit non-zero) |
| Acquisition URL abuse: credentials in URL, host-suffix tricks, `github.com@evil.com`, http, ssh form, semicolon injection, missing repo | FALSIFIED | All rejected by the strict parser before any network use |
| API saved-investigation id traversal (`..%2F`, `%2e%2e%2f`) | FALSIFIED | 404; ids are database keys, never filesystem paths |
| API source confusion (`/etc/passwd`, non-GitHub https URL) | FALSIFIED | 400 with an acquisition/excavation error, no findings fabricated |
| MCP direct tool call on `/etc` | FALSIFIED as a crash vector | Rejected at the excavation boundary; the real contract surface (stdio) is covered by `tests/test_mcp_contract.py` |

## Not run / remaining

- Browser-based stored-XSS attempt with hostile claim text (React
  escaping is the defense; headless verification in Round 5 did not
  include a hostile-text fixture).
- Commit-count truncation probe at 5,000+ commits was not re-run; the
  cap and its warning are covered by unit tests at small limits.
- Concurrency: two simultaneous API investigations writing the shared
  SQLite workspace were not stress-tested.
