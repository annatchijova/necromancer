# Scale benchmark (Round 4)

Bounded behavior for large histories, measured on synthetic fixtures.
VIGÍA has NOT been tested. Its reported size (roughly one million total
lines including documentation and bundles, roughly 102K nonblank,
noncomment Python LOC) is a user-reported approximation, not a verified
measurement, and no performance claim is made about it.

## Design

- One streaming `git log --name-status` pass per excavation replaces the
  previous per-commit subprocess calls. Commit bodies and file lists are
  parsed from that single stream; rename/copy records keep the target
  path.
- Deterministic traversal and sealing are unchanged: the excavation
  result feeds the same canonical, SHA-256-sealed payload.
- Configurable bounds: history is capped (`max_commits`, default 5000)
  and truncation is reported as a warning and in `Excavation.stats`,
  never silent. Text indexing is capped per file (200,000 bytes); files
  above the cap are hashed but not text-indexed, and the skip is counted
  (`texts_skipped_over_cap`) and warned about explicitly.
- Progress (`progress` callback: commits/texts phases) and cooperative
  cancellation (`cancel_event`, raising `ExcavationCancelled`) are
  supported and tested.
- Binary and oversized blobs stream through `git cat-file` in chunks;
  the whole blob is never loaded to hash it (1 MiB streaming bound from
  the Round 3 red team).

## Harness

```bash
python scripts/scale_benchmark.py [commits] [files]
```

Generates a deterministic synthetic repository, excavates it end to end
(excavation plus full investigation), and reports wall time, peak RSS of
the harness process, commits, file-change entries, claims,
contradictions, warnings and skipped texts.

## Measured (this workspace, synthetic, 2026-11-03)

| Generated repo | Wall time | Peak RSS | Claims | Skipped texts |
|---|---|---|---|---|
| 300 commits, 200 files | 0.66 s | 25.3 MB | 2 | 0 |
| 1500 commits, 1000 files | 3.20 s | 30.4 MB | 2 | 0 |

These numbers describe only the generated fixtures above. They are not
a promise about any real repository, and two points do not establish a
scaling law.

## Explicitly not done

- No persistent/reusable on-disk index across investigations; reopening
  a stored investigation avoids re-analysis, re-excavation does not.
- No incremental indexing of changed commits only.
- Cancellation is cooperative between phases, not an interruption of a
  single in-flight Git subprocess.
- Partial-index recovery after a killed process is not implemented;
  a cancelled excavation raises and discards, it does not resume.

## Checkpoint design (deferred, Round 5 decision)

Resumable excavation was investigated and deliberately NOT implemented
this round. A safe design would require: checkpoints bound to
(repository identity, HEAD, snapshot scope, excavation configuration,
schema version); per-stage completion records (commits, texts, claims)
with their own integrity hashes; stale-checkpoint detection on any
mismatch of those bindings; idempotent resume that re-derives, never
trusts, partial claim state; and a hard rule that a partial excavation
is presented as INCOMPLETE with its coverage stated, never as a
finished investigation. The risk that justified deferral: a resumed
half-index silently presented as complete would violate the same
invariant this project exists to protect. Correctness over a resume
button.

## VIGÍA stress test (real repository, Round 5)

Target: `/home/labestiadevigia/vigia-repo` at
`95e1251bf7fab602e3bb87258b550a47594d0c04` (1,247 commits, 3,227 files
in the HEAD tree, ~58 MB of HEAD blobs; working tree 8.8 GB including
data bundles outside HEAD). Read-only HEAD excavation; no VIGÍA code
executed, no dependencies installed, repository not modified (433
pre-existing dirty paths were present before the run and untouched).

Measured in this workspace (investigation end to end):

| Run | Wall | Peak RSS | Claims | CONFIRMED | POTENTIAL |
|---|---|---|---|---|---|
| Pre-repair code | 437 s | 215 MB | 4,685 | 1,098 | 249 |
| After Round 5 repairs | 450 s | 215 MB | 4,685 | 492 | 1,062 |

The pre-repair run exposed two fan-out defects, both fixed and covered
by regression tests: file-only revert overlap confirmed 683
contradictions from 3 real revert commits, and narrative "removed"
prose confirmed as STILL_PRESENT. Health on VIGÍA: ACTIVE (last commit
2 days before the investigation date); it was not classified abandoned,
and no such claim is made. Graph: 16,883 nodes / 35,970 edges; planner:
2,078 actions in 43 groups (grouping is what keeps that output
reviewable at all). Top fan-out: one corpus JSON at graph degree 744.

Stage-level timings (acquisition/extraction/qualification/graph/
planning/export separately), bytes inspected and output size were not
instrumented in this run and are reported as NOT MEASURED rather than
estimated. VIGÍA's user-reported size (~1M total lines, ~102K Python
LOC) was not independently verified; the excavation above is bounded
by HEAD content, not by the 8.8 GB working tree.
