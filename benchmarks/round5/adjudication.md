# Round 5 provisional adjudication artifact

Status of every label in this file: **provisional machine-assisted
adjudication by the same agent that built the system**. This is NOT
independent human ground truth and must not be quoted as measured
real-world precision. It exists so a human investigator can verify or
overturn each line efficiently.

Sampling: stratified by claim state (confirmed contradicted, potential,
supported, unverified), deterministic evenly spaced picks sorted by
claim id. Denominators are the full populations at the recorded
revision. Previously contradicted (Round 4) claims that are no longer
confirmed were sampled as their own stratum on RAVEN-MEMORY/KRAKADYL.

## RAVEN-MEMORY @ 028aa4d2 (population: 3 confirmed, 1 potential-owner, 175 supported, 1 unverified at sampling time)

| Sample | System said | Provisional adjudication | Basis |
|---|---|---|---|
| "`share=True` removed — public gradio.live tunnelling" (FIXES_v1.1.md) vs api_server.py | CONFIRMED STILL_PRESENT (Round 4 code) | UNRESOLVED, leaning true: the doc asserts removal of a launch flag; code inspection is required to settle whether the flag is still passed. Demoted to POTENTIAL by the definition rule (use, not definition). | Claim/evidence read in context; code path not executed. |
| "Non-atomic legacy helpers removed." vs api_server.py | CONFIRMED STILL_PRESENT (Round 4 code) | FALSE POSITIVE (provisional): narrative fix-log prose; no code identifier is named as the deprecated subject. | Sentence names no identifier; generic tokens matched code. |
| "go red when removed." (commit fragment) vs api_server.py | CONFIRMED STILL_PRESENT (Round 4 code) | FALSE POSITIVE (provisional): sentence fragment extracted from a commit message, not a deprecation assertion. | Fragment lacks a subject. |

After the Round 5 definition rule: 0 CONFIRMED, 3 POTENTIAL on this
repository. One likely true contradiction was demoted with the two
false ones; that recall cost is recorded, not hidden.

## KRAKADYL @ 4d319251 (population at sampling: 6 confirmed, 22 potential-owners, 619 supported, 61 unverified)

| Sample | System said | Provisional adjudication | Basis |
|---|---|---|---|
| "In 1991, an airplane lost the leading edge of a stabilizer because one shift removed…" (research EN) vs demo code | CONFIRMED | FALSE POSITIVE: historical narrative prose containing "removed"; not a deprecation claim about code. | Full sentence read; subject is an aircraft component. |
| "`updated_at` is removed from the head ordering." (design doc) vs demo/run_case_001.py | CONFIRMED | FALSE POSITIVE (provisional): design-scope assertion; the identifier lives in an unrelated demo, different scope. | Scope mismatch between design doc and demo evidence. |
| "**Aviation: Continental Express 2574 (1991).** The second shift removed screws…" vs demo code | CONFIRMED | FALSE POSITIVE: narrative prose. | As above. |
| "At least one negative control must show each key gate rejects when removed…" vs demo code | CONFIRMED | FALSE POSITIVE: normative requirement text, not a deprecation. | Sentence is a requirement, not an assertion of removal. |
| "Expired request rows are logically removed…" (design doc) vs demo code | CONFIRMED | FALSE POSITIVE (provisional): design description; demo is not the designed component. | Scope mismatch. |
| "The gate inserts the request record…" with `DISPATCH_INTENT` defined in a demo file | CONFIRMED (still, after the definition rule) | UNRESOLVED: identifier is genuinely defined in code, but the claim's scope is a design document and the definition sits in an adversarial demo file. A human must decide whether that is the same subject. | Definition present; scope unresolved. |

After the Round 5 rules: 1 CONFIRMED (the unresolved one), 29 POTENTIAL.

## VIGÍA @ 95e1251b (population: 4,685 claims; 492 confirmed after repairs)

Sampled: the first 8 confirmed contradictions printed by the probe
(convenience order of the report, NOT a random sample — stated plainly).
All eight are audit/limitations documents (KNOWN_LIMITATIONS.md,
AUDITORIA_*.md) whose claims bind to commits whose files still carry
incomplete markers. Provisional adjudication: UNRESOLVED for all eight.
Each requires reading the audit context and the bound commit; several
plausibly describe real incomplete fixes in a security tool's own audit
history, and several plausibly bind by vocabulary alone. No precision
figure is derived from them.

Shared-evidence fan-out on VIGÍA (observed): a single corpus JSON file
carries degree 744 in the graph; KNOWN_LIMITATIONS.md degree 346;
BUGS_PENDIENTES.md degree 308. Any contradiction resting on those files
inherits their binding risk and is flagged in the UI.

## What would resolve the open items

Independent human adjudication of: the RAVEN `share=True` case, the
KRAKADYL `DISPATCH_INTENT` case, and a random (not first-eight) sample
of at least 30 VIGÍA confirmed contradictions with recorded inter-rater
agreement. Until then, real-world precision remains unmeasured.
