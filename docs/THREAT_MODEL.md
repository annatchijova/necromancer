# Threat model

NECROMANCER investigates repositories it must assume are hostile, on a
machine that holds other private work. This model covers the local,
acquisition, persistence, API, MCP and optional-model surfaces.

## Assets

- The invoking user's filesystem outside the target repository.
- Other repositories and credentials on the same machine.
- The integrity of the evidence record: seals, ledger, stored reports.
- The user's attention: a falsely confident report is an integrity loss.

## Actors and authority

| Actor | Authority |
|-------|-----------|
| Operator (CLI user) | Full local authority. Chooses targets and providers. |
| Local API client | Whoever can reach the loopback port. The API is unauthenticated by design and must never be exposed beyond loopback without an added authority layer. |
| MCP client | The local process that launched the server over stdio. It is the principal; its tool calls are authorized, the data returned is not thereby trusted. |
| Target repository | Untrusted data. No authority, ever: files, filenames, commit messages, Git config, attributes and symlinks are evidence, never instructions. |
| Model provider | Untrusted interpreter. Receives only the sealed summary when the operator opts in; returns text that is parsed strictly and labeled `HYPOTHESIS`. |
| GitHub (acquisition) | Untrusted transport and content source. Only reachability and clone integrity are assumed, never content truth. |

## Boundaries and controls

### Excavation boundary

- Allowlisted read-only Git subcommands only, arguments as lists, never
  a shell. Repository code, hooks, filters and submodules never execute.
- `head` scope reads committed blobs via streaming `git cat-file`;
  `worktree` scope reads disk, reports divergence, and never follows a
  tracked symlink outside the tree (its content is the link string).
- Filenames are handled NUL-delimited; blobs are hashed incrementally
  with a text-indexing cap; commit history is capped.
- Prompt injection in repository content is claim data. Verdicts come
  from deterministic policy, so injected text cannot promote itself.

### Acquisition boundary

- Only `https://github.com/<owner>/<repo>` passes validation: no other
  host, scheme, port, credentials, query, fragment or traversal, and no
  shell metacharacters. This is enforced in one parser used by CLI, API
  and MCP alike, so no surface can widen it.
- Clone runs with prompts and credential helpers disabled, system Git
  config ignored, `--no-checkout --single-branch --no-recurse-submodules`,
  depth 500 and a 200 MB tree cap, under a timeout, into an isolated
  temporary workspace. Partial workspaces are deleted on any failure.
- Acquisition failures are `AcquisitionError`: operational errors,
  never forensic findings, and credentials never enter artifacts.

### Persistence boundary

- Investigations live in a local SQLite database (operator-controlled
  path or `NECROMANCER_DB`). Stored reports contain repository paths and
  claim texts quoted from the target: treat the database as sensitive
  local evidence, with filesystem permissions as its access control.
- Stored evidence is keyed by seal and never silently replaced;
  reopening reports `CURRENT` or `STALE`. Deletion is an explicit,
  single-investigation operation initiated by the operator.

### Model boundary

- Offline is the default and needs no credentials or network. Hosted or
  local providers are operator-configured endpoints; the sealed summary
  they receive can quote claim text from the target, so enabling one is
  an explicit egress decision by the operator.
- Model output is size-capped, schema-parsed and stored only as
  `HYPOTHESIS` beside the seal. It cannot execute tools, change claim
  states, or fabricate accepted citations: links come from the
  deterministic layer, never from the model.

## Resource limits

| Resource | Limit |
|----------|-------|
| Commits excavated | 5,000 |
| Text indexed per file | 200 KB (hashing is streamed, uncapped size) |
| Clone depth / size / time | 500 commits / 200 MB / 120 s |
| Hypotheses per provider response | 50 |

## Out of scope and residual risk

- A local attacker who can already run processes as the user is out of
  scope; NECROMANCER adds no privilege separation inside one account.
- The loopback API inherits the machine's local trust. Exposing it is
  an operator error this design does not defend against yet.
- Git itself parses hostile objects during clone and excavation. Keeping
  Git patched is an environment responsibility; NECROMANCER minimizes
  the operations it asks Git to perform but cannot sandbox the parser.
- A seal proves the evidence record was not altered after sealing. It
  has never proved the recorded claims are true.
