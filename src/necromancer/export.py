"""JSON and Markdown export. Provenance travels with every claim."""

from __future__ import annotations

import json
from collections import Counter

from .models import Report


def report_to_dict(report: Report) -> dict:
    return {
        "repo_path": report.repo_path,
        "head": report.head,
        "snapshot": report.snapshot,
        "source_kind": report.source_kind,
        "source_ref": report.source_ref,
        "health": report.health,
        "graph": report.graph,
        "seal": report.seal,
        "warnings": list(report.warnings),
        "events": [
            {"id": e.event_id, "ts": e.ts_iso, "kind": e.kind, "title": e.title,
             "detail": e.detail, "refs": list(e.refs), "provenance": e.provenance.value}
            for e in report.events
        ],
        "claims": [
            {"id": c.claim_id, "text": c.text, "verb": c.verb, "state": c.state.value,
             "source_kind": c.source_kind, "source_ref": c.source_ref, "origin": c.origin,
             "line": c.line, "extraction": c.extraction,
             "modality": c.modality, "subject_tokens": list(c.subject_tokens),
             "scope": c.scope, "falsifier": c.falsifier, "rationale": c.rationale}
            for c in report.claims
        ],
        "links": [
            {"claim_id": link.claim_id, "evidence_ref": link.evidence_ref,
             "relation": link.relation.value, "rationale": link.rationale,
             "binding_score": link.binding_score, "match_basis": link.match_basis,
             "binding_meaning": "token-overlap strength, not a calibrated probability"}
            for link in report.links
        ],
        "contradictions": [
            {"id": c.contradiction_id, "claim_id": c.claim_id,
             "evidence_ref": c.evidence_ref, "kind": c.kind, "detail": c.detail,
             "qualification": c.qualification}
            for c in report.contradictions
        ],
        "hypotheses_not_facts": [
            {"id": h.hypothesis_id, "group": h.group_id, "question": h.question,
             "statement": h.statement, "discriminators": list(h.discriminators),
             "confidence": f"{h.confidence.numerator}/{h.confidence.denominator}",
             "provenance": h.provenance.value}
            for h in report.hypotheses
        ],
        "resurrection_plan": [
            {"id": a.action_id, "priority": a.priority, "title": a.title,
             "rationale": a.rationale, "claim_ids": list(a.claim_ids),
             "reversible": a.reversible, "suggested_check": a.suggested_check,
             "risk": a.risk, "prerequisites": a.prerequisites,
             "expected_effect": a.expected_effect, "group": a.group}
            for a in report.actions
        ],
        "abandoned_branches": [
            {"name": b.name, "tip": b.tip, "merged_into_head": b.merged_into_head}
            for b in report.abandoned_branches
        ],
    }


def to_json(report: Report) -> str:
    return json.dumps(report_to_dict(report), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")[:160]


def to_markdown(report: Report) -> str:
    counts = Counter(claim.state.value for claim in report.claims)
    lines: list[str] = [
        "# NECROMANCER investigation report",
        "",
        "## Scope and methodology",
        "",
        f"Repository: `{report.repo_path}` at `{report.head[:12]}`",
        f"Source: {report.source_kind} {report.source_ref}".strip(),
        f"Snapshot scope: {report.snapshot} (head = committed blobs; worktree = disk plus divergence)",
        "Method: read-only Git excavation, deterministic claim-evidence rules, "
        "sealed before any model interpretation. Target code and tests were never executed.",
        "The seal proves evidence integrity, not factual truth.",
        "",
        f"Evidence seal (SHA-256): `{report.seal}`",
        "",
        "Reproduce: run `necromancer excavate` on the same repository and "
        "snapshot, then compare the seal.",
        "",
        "Claim counts by epistemic level (never collapsed into one number):",
        "",
    ]
    if report.health:
        lines += [
            "## Repository health indicators (not a verdict)",
            "",
            f"Category: {report.health.get('category')} — "
            f"{'; '.join(report.health.get('category_evidence', []))}",
            f"Last commit: {report.health.get('last_commit')} "
            f"({report.health.get('days_since_last_commit')} days before investigation)",
            f"Unmerged branches: {', '.join(report.health.get('unmerged_branches', [])) or 'none'}",
            f"TODO/FIXME references: {report.health.get('todo_fixme_references')}; "
            f"test files: {report.health.get('test_files')}; "
            f"CI config present: {report.health.get('ci_config_present')}",
            "",
        ]
    for state in ("VERIFIED", "SUPPORTED", "CONTRADICTED", "UNVERIFIED", "NOT_DETERMINABLE"):
        lines.append(f"- {state}: {counts.get(state, 0)}")
    if report.warnings:
        lines += ["", "## Warnings", ""] + [f"- WARN: {item}" for item in report.warnings]
    lines += ["", "## Timeline", "",
              "Times are recorded Git author dates (one clock domain). Order is "
              "adjacency, not causation. Gaps mean no event was recorded, not "
              "that nothing happened.", "",
              "| When | Kind | Event | Evidence |", "|---|---|---|---|"]
    for event in report.events:
        lines.append(f"| {_cell(event.ts_iso)} | {event.kind} | {_cell(event.title)} | {_cell(', '.join(event.refs[:3]))} |")
    lines += ["", "## Claims", ""]
    for claim in report.claims:
        lines += [
            f"### {claim.claim_id} — {claim.state.value}",
            "",
            f"> {_cell(claim.text)}",
            "",
            f"- Origin: `{claim.origin or claim.source_ref}` ({claim.source_kind})",
            f"- Level: {claim.state.value} — {claim.rationale}",
            f"- Scope: {claim.scope}",
            f"- Falsifier: {claim.falsifier or 'not recorded'}",
            "",
        ]
    lines += ["## Contradictions and potential conflicts", "",
              "CONFIRMED entries state a defensible incompatibility and changed "
              "the claim state. POTENTIAL entries are unreviewed conflicts; they "
              "changed nothing and are not findings.", ""]
    if not report.contradictions:
        lines.append("None detected by the deterministic rules. This is not proof that none exist.")
    for item in report.contradictions:
        lines.append(
            f"- [{item.kind} · {item.qualification}] claim `{item.claim_id}` vs "
            f"`{item.evidence_ref}`: {item.detail} "
            "(CONFIRMED changes the claim state; POTENTIAL is a review queue entry.)")
    lines += ["", "## Hypotheses — not facts", "",
              "Model or template proposals only. They explain evidence; they never upgrade it.", ""]
    for hyp in report.hypotheses:
        lines.append(
            f"- ({hyp.confidence}) {hyp.statement} "
            f"Discriminate by: {'; '.join(hyp.discriminators)}"
        )
    lines += ["", "## Resurrection plan (grouped by root cause)", ""]
    for action in report.actions:
        lines.append(
            f"- P{action.priority} [{action.group}] {action.title} "
            f"Claims: {', '.join(action.claim_ids) or 'none'}. Check: {action.suggested_check}")
    lines += ["", "## Limits", "",
              "Target code and tests were not executed. VERIFIED is never issued from "
              "token presence alone; trusted execution evidence is required. See docs.", ""]
    return "\n".join(lines)
