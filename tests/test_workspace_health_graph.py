import pytest

"""Persistent workspaces, health indicators and the evidence graph."""

from datetime import datetime, timezone

from necromancer import workspace
from necromancer.cli import investigate
from necromancer.export import report_to_dict


def test_workspace_roundtrip_compare_and_staleness(synthetic, tmp_path):
    conn = workspace.connect(tmp_path / "inv.db")
    assert workspace.schema_version(conn) == 1
    first = report_to_dict(investigate(str(synthetic["a"])))
    inv_id = workspace.save(conn, first)
    assert workspace.list_investigations(conn)[0]["id"] == inv_id
    reopened = workspace.get(conn, inv_id)
    assert reopened["seal"] == first["seal"], "reopening must never rewrite evidence"
    assert workspace.staleness(conn, inv_id, first["head"]) == "CURRENT"
    assert workspace.staleness(conn, inv_id, "0" * 40) == "STALE"
    diff = workspace.compare(first, first)
    assert diff["changed_claims"] == []
    assert workspace.manifest(first)["seal"] == first["seal"]
    assert workspace.delete(conn, inv_id) is True
    assert workspace.get(conn, inv_id) is None
    conn.close()


def test_health_never_calls_inactivity_abandonment(synthetic):
    report = investigate(str(synthetic["a"]))
    assert report.health["category"] in (
        "STATUS_UNKNOWN", "ACTIVE", "DORMANT", "EXPLICITLY_ABANDONED",
        "MAINTENANCE_ONLY", "SUPERSEDED", "ARCHIVED")
    assert report.health["commit_count"] >= 2
    assert "never proves" in report.health["note"]


def test_graph_is_typed_and_consistent(synthetic):
    report = investigate(str(synthetic["c"]))
    graph = report.graph
    node_ids = {node["id"] for node in graph["nodes"]}
    assert graph["relationships"], "relationship semantics must be documented"
    for edge in graph["edges"]:
        assert edge["source"] in node_ids, f"dangling source {edge['source']}"
        assert edge["target"] in node_ids, f"dangling target {edge['target']}"
        assert edge["relation"] in graph["relationships"]
    speculative = [e for e in graph["edges"] if e["relation"] == "HYPOTHESIZED_CAUSE"]
    assert speculative and all(e["speculative"] for e in speculative)
    assert any(e["relation"] == "CONTRADICTED_BY" for e in graph["edges"])


def test_graph_views_clusters_fanout_and_focus(synthetic):
    report = investigate(str(synthetic["c"]))
    graph = report.graph
    assert graph["clusters"]["claims_by_state"], "claims must cluster by state"
    assert graph["clusters"]["files_by_subsystem"], "files must cluster by subsystem"
    for claim_id, neighbours in graph["focus"].items():
        assert claim_id.startswith("claim:")
        assert neighbours, "a focused claim must show its neighbourhood"
    for entry in graph["fanout"]:
        assert entry["degree"] >= 3 and "shared evidence" in entry["warning"]


def test_planner_groups_share_one_action_per_root_cause(synthetic):
    report = investigate(str(synthetic["a"]))
    groups = [action.group for action in report.actions]
    assert all(group != "general" for group in groups), groups
    verify_actions = [a for a in report.actions if a.group.startswith("contradiction:")]
    claimed = [cid for a in verify_actions for cid in a.claim_ids]
    assert len(claimed) == len(set(claimed)), "claims must not repeat across actions"


def test_investigation_timestamp_is_outside_seal(synthetic):
    # Health uses investigation time; the seal must not depend on it.
    first = investigate(str(synthetic["b"]))
    second = investigate(str(synthetic["b"]))
    assert first.seal == second.seal


def test_excavation_cancellation_and_limits(synthetic) -> None:
    import threading

    from necromancer.excavator import ExcavationCancelled, excavate

    cancelled = threading.Event()
    cancelled.set()
    with pytest.raises(ExcavationCancelled):
        excavate(synthetic['a'], cancel_event=cancelled)
    limited = excavate(synthetic['a'], max_commits=1)
    assert len(limited.commits) == 1
    assert any('truncated' in w for w in limited.warnings)
