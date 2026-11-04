"""Chronology reconstruction: provenance-linked events, deterministically ordered."""

from __future__ import annotations

import hashlib

from .excavator import Excavation
from .models import Event, Provenance


def _event_id(kind: str, ref: str) -> str:
    return hashlib.sha256(f"{kind}:{ref}".encode("utf-8")).hexdigest()[:16]


def build_events(excavation: Excavation) -> list[Event]:
    events: list[Event] = []
    by_hash = {commit.commit_hash: commit for commit in excavation.commits}
    for commit in excavation.commits:
        refs = [commit.commit_hash] + [path for _status, path in commit.files]
        events.append(Event(
            event_id=_event_id("COMMIT", commit.commit_hash),
            ts_iso=commit.date_iso,
            kind="COMMIT",
            title=commit.subject,
            detail=(commit.body or "")[:500],
            refs=tuple(refs),
            provenance=Provenance.EXTRACTED,
        ))
    for name, tip in excavation.tags:
        tagged = by_hash.get(tip)
        events.append(Event(
            event_id=_event_id("TAG", f"{name}:{tip}"),
            ts_iso=tagged.date_iso if tagged else "",
            kind="TAG",
            title=f"Tag {name}",
            detail=f"Points at {tip[:12]}",
            refs=(tip,),
            provenance=Provenance.EXTRACTED,
        ))
    for branch in excavation.branches:
        if branch.merged_into_head:
            continue
        tip_commit = by_hash.get(branch.tip)
        events.append(Event(
            event_id=_event_id("BRANCH", f"{branch.name}:{branch.tip}"),
            ts_iso=tip_commit.date_iso if tip_commit else "",
            kind="UNMERGED_BRANCH",
            title=f"Unmerged branch {branch.name}",
            detail=f"Tip {branch.tip[:12]} is not merged into HEAD",
            refs=(branch.tip, branch.name),
            provenance=Provenance.EXTRACTED,
        ))
    events.sort(key=lambda event: (event.ts_iso, event.event_id))
    return events
