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
- History is read from the local clone as given. A shallow clone, a
  rewritten history, or work that only ever existed in an issue tracker
  is invisible here and is reported as missing evidence, never as proof
  that it did not happen.
- The hosted-model provider is an adapter boundary. Without configured
  credentials the system stays in deterministic offline mode and says so.
  No model output is ever invented to fill the gap.
- File contents are indexed up to a size cap; very large artifacts are
  hashed but not text-searched, which can lower a claim to `UNVERIFIED`.
