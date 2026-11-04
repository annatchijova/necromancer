"""Evidence model. Every statement carries provenance and uncertainty."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction


class Provenance(StrEnum):
    EXTRACTED = "EXTRACTED"
    DERIVED = "DERIVED"
    HYPOTHESIS = "HYPOTHESIS"


class ClaimState(StrEnum):
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNVERIFIED = "UNVERIFIED"
    NOT_DETERMINABLE = "NOT_DETERMINABLE"


class Relation(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"


@dataclass(frozen=True)
class Artifact:
    path: str
    sha256: str
    size: int
    kind: str  # DOC, TEST, CODE, OTHER


@dataclass(frozen=True)
class CommitRecord:
    commit_hash: str
    parents: tuple[str, ...]
    author: str
    date_iso: str
    subject: str
    body: str
    files: tuple[tuple[str, str], ...]  # (status, path)


@dataclass(frozen=True)
class BranchInfo:
    name: str
    tip: str
    merged_into_head: bool


@dataclass(frozen=True)
class Event:
    event_id: str
    ts_iso: str
    kind: str
    title: str
    detail: str
    refs: tuple[str, ...]
    provenance: Provenance = Provenance.EXTRACTED


@dataclass
class Claim:
    claim_id: str
    text: str
    source_kind: str  # DOC or COMMIT
    source_ref: str
    verb: str
    state: ClaimState = ClaimState.UNVERIFIED
    rationale: str = ""
    # Provenance attributes that must travel with the claim, never stripped:
    origin: str = ""  # exact source pointer (file path or commit)
    scope: str = "HEAD tree at excavation time; target code and tests not executed"
    falsifier: str = ""  # evidence that would reopen or change this verdict


@dataclass(frozen=True)
class EvidenceLink:
    claim_id: str
    evidence_ref: str
    relation: Relation
    rationale: str


@dataclass(frozen=True)
class Contradiction:
    contradiction_id: str
    claim_id: str
    evidence_ref: str
    kind: str
    detail: str


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    group_id: str
    question: str
    statement: str
    discriminators: tuple[str, ...]
    confidence: Fraction = Fraction(1, 3)
    provenance: Provenance = Provenance.HYPOTHESIS


@dataclass(frozen=True)
class PlanAction:
    action_id: str
    priority: int  # 0 is most urgent
    title: str
    rationale: str
    claim_ids: tuple[str, ...]
    reversible: bool = True
    suggested_check: str = ""


@dataclass
class Report:
    repo_path: str
    head: str
    snapshot: str = "head"  # head (committed blobs) or worktree (disk + divergence report)
    events: list[Event] = field(default_factory=list)
    claims: list[Claim] = field(default_factory=list)
    links: list[EvidenceLink] = field(default_factory=list)
    contradictions: list[Contradiction] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    actions: list[PlanAction] = field(default_factory=list)
    abandoned_branches: list[BranchInfo] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seal: str = ""

    def sealable_payload(self) -> dict:
        """Deterministic payload sealed before any model narration exists."""
        return {
            "repo_path": self.repo_path,
            "head": self.head,
            "snapshot": self.snapshot,
            "events": [
                (e.event_id, e.ts_iso, e.kind, e.title, e.refs) for e in self.events
            ],
            "claims": [
                (c.claim_id, c.text, c.source_ref, c.verb, c.state.value)
                for c in self.claims
            ],
            "links": [
                (link.claim_id, link.evidence_ref, link.relation.value)
                for link in self.links
            ],
            "contradictions": [
                (c.contradiction_id, c.claim_id, c.evidence_ref, c.kind)
                for c in self.contradictions
            ],
            "abandoned": [(b.name, b.tip) for b in self.abandoned_branches],
        }
