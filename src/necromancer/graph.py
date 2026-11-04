"""Explainable evidence graph: a projection, never the source of truth.

Typed relationships only. DOCUMENTED SEMANTICS:
- SUPPORTED_BY: claim -> evidence that supports it (deterministic link).
- CONTRADICTED_BY: claim -> positive contradicting evidence.
- INTRODUCED_IN / MODIFIED_IN: file -> commit that added or modified it.
- REFERENCES: claim -> its source file or commit.
- HYPOTHESIZED_CAUSE: hypothesis -> claim it proposes to explain
  (speculative by construction, always labeled).
- REQUIRES_VERIFICATION: recovery action -> claim it must verify first.
"""

from __future__ import annotations

from .excavator import Excavation
from .models import Relation, Report

RELATIONSHIPS = (
    "SUPPORTED_BY", "CONTRADICTED_BY", "INTRODUCED_IN", "MODIFIED_IN",
    "REFERENCES", "HYPOTHESIZED_CAUSE", "REQUIRES_VERIFICATION",
)


def build_graph(report: Report, excavation: Excavation) -> dict:
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(node_id: str, kind: str, label: str, **extra) -> str:
        if node_id not in nodes:
            nodes[node_id] = {"id": node_id, "kind": kind, "label": label[:120], **extra}
        return node_id

    def edge(source: str, target: str, relation: str, speculative: bool = False) -> None:
        edges.append({
            "source": source, "target": target, "relation": relation,
            "speculative": speculative,
        })

    for commit in excavation.commits:
        commit_id = node(f"commit:{commit.commit_hash[:12]}", "commit",
                         commit.subject or commit.commit_hash[:8],
                         ref=commit.commit_hash, ts=commit.date_iso)
        for status, path in commit.files:
            file_id = node(f"file:{path}", "file", path, ref=path)
            edge(file_id, commit_id,
                 "INTRODUCED_IN" if status.startswith("A") else "MODIFIED_IN")
    for branch in excavation.branches:
        node(f"branch:{branch.name}", "branch", branch.name,
             ref=branch.tip, merged=branch.merged_into_head)
    for name, tip in excavation.tags:
        node(f"tag:{name}", "tag", name, ref=tip)
    for event in report.events:
        node(f"event:{event.event_id}", "event", event.title, ref=event.event_id,
             ts=event.ts_iso, kind_detail=event.kind)
    for claim in report.claims:
        claim_id = node(f"claim:{claim.claim_id}", "claim", claim.text,
                        state=claim.state.value, origin=claim.origin,
                        line=claim.line, extraction=claim.extraction)
        source = (
            f"file:{claim.source_ref}" if claim.source_kind == "DOC"
            else f"commit:{claim.source_ref}"
        )
        node(source, "file" if claim.source_kind == "DOC" else "commit",
             claim.source_ref, ref=claim.source_ref)
        edge(claim_id, source, "REFERENCES")
    for link in report.links:
        target = link.evidence_ref
        target_id = (
            f"file:{target}" if ("/" in target or "." in target.split(":")[0])
            else f"commit:{target}"
        )
        node(target_id, "evidence", target, ref=target)
        edge(f"claim:{link.claim_id}", target_id,
             "SUPPORTED_BY" if link.relation == Relation.SUPPORTS else "CONTRADICTED_BY")
    for item in report.contradictions:
        contra_id = node(f"contradiction:{item.contradiction_id}", "contradiction",
                         item.kind, ref=item.evidence_ref, detail=item.detail)
        edge(f"claim:{item.claim_id}", contra_id, "CONTRADICTED_BY")
    for hyp in report.hypotheses:
        hyp_id = node(f"hypothesis:{hyp.hypothesis_id}", "hypothesis", hyp.statement,
                      provenance="HYPOTHESIS", group=hyp.group_id)
        for claim in report.claims:
            if hyp.group_id in (f"claim:{claim.claim_id}",
                                f"unverified:{claim.claim_id}"):
                edge(hyp_id, f"claim:{claim.claim_id}",
                     "HYPOTHESIZED_CAUSE", speculative=True)
    for action in report.actions:
        action_id = node(f"action:{action.action_id}", "action", action.title,
                         priority=action.priority)
        for claim_id in action.claim_ids:
            edge(action_id, f"claim:{claim_id}", "REQUIRES_VERIFICATION")

    edges.sort(key=lambda item: (item["source"], item["target"], item["relation"]))
    return {
        "nodes": sorted(nodes.values(), key=lambda item: item["id"]),
        "edges": edges,
        "relationships": list(RELATIONSHIPS),
        "note": "Projection of the investigation. Speculative edges are labeled and never upgrade evidence.",
    }
