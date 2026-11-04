"""Resurrection planner: reversible, low-risk recovery steps first.

The planner only proposes. It never executes anything against the target
repository.
"""

from __future__ import annotations

import hashlib

from .models import ClaimState, Contradiction, PlanAction, Report


def _aid(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _subsystem(claim) -> str:
    origin = (claim.origin or claim.source_ref or "").split(":")[0]
    parts = [part for part in origin.split("/") if part]
    return parts[0] if len(parts) > 1 else "root"


def build_plan(report: Report) -> list[PlanAction]:
    actions: list[PlanAction] = []
    # Group contradicted claims by shared contradicting evidence and kind:
    # fifty claims contradicted by the same marker are one root cause to
    # review, not fifty near-identical tasks (Round 4 planner requirement).
    by_contradiction: dict[str, Contradiction] = {
        item.claim_id: item for item in report.contradictions
    }
    contradicted_groups: dict[tuple[str, str], list] = {}
    for claim in report.claims:
        if claim.state != ClaimState.CONTRADICTED:
            continue
        item = by_contradiction.get(claim.claim_id)
        key = (item.kind, item.evidence_ref) if item else ("CONTRADICTED", claim.source_ref)
        contradicted_groups.setdefault(key, []).append(claim)
    for (kind, evidence_ref), claims in sorted(contradicted_groups.items()):
        claim_ids = tuple(sorted(claim.claim_id for claim in claims))
        first = claims[0]
        suffix = f" (+{len(claims) - 1} more sharing this evidence)" if len(claims) > 1 else ""
        actions.append(PlanAction(
            action_id=_aid("verify-group:" + ",".join(claim_ids)),
            priority=0,
            title=f"Verify contradicted claim before any new work: {first.text[:70]}{suffix}",
            rationale=first.rationale,
            claim_ids=claim_ids,
            reversible=True,
            suggested_check=f"Inspect the contradicting evidence at {evidence_ref} and re-run the excavation.",
            group=f"contradiction:{kind}:{evidence_ref}",
        ))
    for claim in report.claims:
        if claim.state == ClaimState.CONTRADICTED:
            continue
        if claim.state == ClaimState.SUPPORTED and claim.verb in ("FIXED", "RESOLVED"):
            actions.append(PlanAction(
                action_id=_aid(f"regression:{claim.claim_id}"),
                priority=1,
                title=f"Add the missing regression test for: {claim.text[:70]}",
                rationale="Fix is documented but verification was not demonstrated.",
                claim_ids=(claim.claim_id,),
                reversible=True,
                suggested_check="Write a failing test for the original problem first, then confirm the current code passes it.",
                risk="low: adds a test in your own working copy; executes nothing here",
                prerequisites="A working copy under your control and the original problem report",
                expected_effect="The fix gains a regression oracle that can fail",
                group=f"regression-test:{_subsystem(claim)}",
            ))
        elif claim.state == ClaimState.UNVERIFIED:
            actions.append(PlanAction(
                action_id=_aid(f"locate:{claim.claim_id}"),
                priority=1,
                title=f"Locate evidence for unverified claim: {claim.text[:70]}",
                rationale=claim.rationale,
                claim_ids=(claim.claim_id,),
                reversible=True,
                suggested_check="Search all branches, tags and documents for the claim tokens before concluding anything.",
                group=f"unverified:{_subsystem(claim)}",
            ))
        elif claim.state == ClaimState.NOT_DETERMINABLE:
            actions.append(PlanAction(
                action_id=_aid(f"context:{claim.claim_id}"),
                priority=2,
                title=f"Recover missing context for: {claim.text[:70]}",
                rationale=claim.rationale,
                claim_ids=(claim.claim_id,),
                reversible=True,
                suggested_check="Ask former maintainers or linked issues; record the answer as new evidence, not as memory.",
                group=f"context-recovery:{_subsystem(claim)}",
            ))
    for branch in report.abandoned_branches:
        actions.append(PlanAction(
            action_id=_aid(f"branch:{branch.name}"),
            priority=0,
            title=f"Inspect unmerged branch {branch.name} before discarding it",
            rationale=f"Branch tip {branch.tip[:8]} is not merged into HEAD and may contain lost work.",
            claim_ids=(),
            reversible=True,
            suggested_check=f"git diff HEAD...{branch.name} (read-only) and list files unique to the branch.",
            risk="low: read-only diff; merging is a separate human decision",
            prerequisites="The branch ref still exists locally",
            expected_effect="Lost work on the branch is identified before any discard",
            group="unmerged-branches",
        ))
    actions.sort(key=lambda action: (action.priority, action.action_id))
    return actions
