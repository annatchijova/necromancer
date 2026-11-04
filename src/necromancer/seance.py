"""Abductive hypothesis engine.

Hypotheses are generated only after the deterministic report is sealed.
They carry Provenance.HYPOTHESIS, present competing explanations, and name
the observations that would discriminate between them. They can never
change a claim state.
"""

from __future__ import annotations

import hashlib
import os
from fractions import Fraction
from typing import Protocol

from .models import ClaimState, Hypothesis, Provenance, Report


class HypothesisProvider(Protocol):
    def generate(self, report: Report) -> list[Hypothesis]:
        ...


def _hid(group: str, index: int) -> str:
    return hashlib.sha256(f"{group}|{index}".encode("utf-8")).hexdigest()[:16]


def _group(report: Report, group_id: str, question: str, options: list[tuple[str, tuple[str, ...]]]) -> list[Hypothesis]:
    share = Fraction(1, len(options))
    return [
        Hypothesis(
            hypothesis_id=_hid(group_id, index),
            group_id=group_id,
            question=question,
            statement=statement,
            discriminators=discriminators,
            confidence=share,
            provenance=Provenance.HYPOTHESIS,
        )
        for index, (statement, discriminators) in enumerate(options)
    ]


class OfflineTemplateProvider:
    """Deterministic offline hypotheses. Useful without any API key."""

    name = "offline-templates"

    def generate(self, report: Report) -> list[Hypothesis]:
        out: list[Hypothesis] = []
        for claim in report.claims:
            if claim.state != ClaimState.CONTRADICTED:
                continue
            out.extend(_group(
                report, f"claim:{claim.claim_id}",
                f"Why is this claim contradicted: {claim.text[:90]}",
                [
                    ("The change was partial: it addressed part of the problem and was documented as complete.",
                     ("Inspect the full diff of the referenced commit.", "Check whether the touched files still carry incomplete markers.")),
                    ("The change was complete but later regressed or was reverted.",
                     ("List later commits touching the same files.", "Look for a revert commit after the fix date.")),
                    ("The documentation was aspirational and ran ahead of the code.",
                     ("Compare the document date with the commit dates.", "Check whether any commit implements the documented behaviour.")),
                ],
            ))
        for branch in report.abandoned_branches:
            out.extend(_group(
                report, f"branch:{branch.name}",
                f"What does unmerged branch {branch.name} contain?",
                [
                    ("The branch contains the missing solution and was never merged.",
                     (f"Read the diff with: git diff HEAD...{branch.name}", "Check for test files that only exist on the branch.")),
                    ("The branch is a stale duplicate of work already on HEAD.",
                     ("Compare the branch tip date with HEAD history.", "Check whether the same change exists under another commit on HEAD.")),
                    ("The branch was an experiment that was deliberately abandoned.",
                     ("Read the branch commit messages for abandonment signals.", "Check whether the branch introduces dependencies later removed.")),
                ],
            ))
        unverified = [c for c in report.claims if c.state == ClaimState.UNVERIFIED][:5]
        for claim in unverified:
            out.extend(_group(
                report, f"unverified:{claim.claim_id}",
                f"Why is no evidence available for: {claim.text[:90]}",
                [
                    ("The work happened but was never recorded in this repository.",
                     ("Search branches and tags for related commits.", "Look for references in issue or changelog text.")),
                    ("The work never happened; the claim anticipated it.",
                     ("Search the full history for the feature tokens.", "Compare claim date with the last related commit.")),
                ],
            ))
        out.sort(key=lambda item: (item.group_id, item.hypothesis_id))
        return out


class ClaudeHypothesisProvider:
    """Adapter boundary for a hosted model. Never fakes a result.

    Without credentials it fails loudly so the caller stays in honest
    offline mode. The sealed report summary is the only input a model may
    receive; its output can only ever become Provenance.HYPOTHESIS rows.
    """

    name = "claude"

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("NECROMANCER_CLAUDE_API_KEY", "")
        self.model = model or os.environ.get("NECROMANCER_CLAUDE_MODEL", "")

    def generate(self, report: Report) -> list[Hypothesis]:
        if not self.api_key or not self.model:
            raise RuntimeError(
                "Claude provider is not configured (NECROMANCER_CLAUDE_API_KEY / "
                "NECROMANCER_CLAUDE_MODEL missing). Staying in offline mode."
            )
        raise RuntimeError(
            "Claude transport is not wired in this level. Offline hypotheses remain "
            "available and no model output was invented."
        )
