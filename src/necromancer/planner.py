"""Resurrection planner: reversible, low-risk recovery steps first.

The planner only proposes. It never executes anything against the target
repository.
"""

from __future__ import annotations

import hashlib

from .models import ClaimState, PlanAction, Report


def _aid(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def build_plan(report: Report) -> list[PlanAction]:
    actions: list[PlanAction] = []
    for claim in report.claims:
        if claim.state == ClaimState.CONTRADICTED:
            actions.append(PlanAction(
                action_id=_aid(f"verify:{claim.claim_id}"),
                priority=0,
                title=f"Verify contradicted claim before any new work: {claim.text[:70]}",
                rationale=claim.rationale,
                claim_ids=(claim.claim_id,),
                reversible=True,
                suggested_check=f"Inspect the contradicting evidence at {claim.source_ref} and re-run the excavation.",
            ))
        elif claim.state == ClaimState.SUPPORTED and claim.verb in ("FIXED", "RESOLVED"):
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
        ))
    actions.sort(key=lambda action: (action.priority, action.action_id))
    return actions
