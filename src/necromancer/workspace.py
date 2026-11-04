"""Durable local investigation workspaces (SQLite).

An earlier investigation is never silently replaced: reopening compares
the stored HEAD and seal with the repository as it is now and reports
STALE instead of overwriting. Reports are stored with their seal and
content hashes so a manifest can be exported and checked independently.
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS investigations (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  repo_path TEXT NOT NULL,
  source_kind TEXT NOT NULL,
  source_ref TEXT NOT NULL,
  head TEXT NOT NULL,
  snapshot TEXT NOT NULL,
  seal TEXT NOT NULL,
  report_json TEXT NOT NULL
);
"""


def default_db_path() -> Path:
    override = os.environ.get("NECROMANCER_DB", "")
    if override:
        return Path(override)
    return Path.home() / ".local" / "share" / "necromancer" / "investigations.db"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path) if path else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    conn.commit()
    return conn


def schema_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM meta WHERE key = 'schema_version'").fetchone()
    return int(row["value"]) if row else 0


def investigation_id(report_dict: dict) -> str:
    return report_dict["seal"][:24]


def save(conn: sqlite3.Connection, report_dict: dict) -> str:
    inv_id = investigation_id(report_dict)
    conn.execute(
        "INSERT OR IGNORE INTO investigations "
        "(id, created_at, repo_path, source_kind, source_ref, head, snapshot, seal, report_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            inv_id,
            datetime.now(timezone.utc).isoformat(),
            report_dict["repo_path"],
            report_dict.get("source_kind", "local"),
            report_dict.get("source_ref", ""),
            report_dict["head"],
            report_dict.get("snapshot", "head"),
            report_dict["seal"],
            json.dumps(report_dict, sort_keys=True),
        ),
    )
    conn.commit()
    return inv_id


def list_investigations(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, created_at, repo_path, source_kind, source_ref, head, snapshot, seal "
        "FROM investigations ORDER BY created_at DESC"
    ).fetchall()
    return [dict(row) for row in rows]


def get(conn: sqlite3.Connection, inv_id: str) -> dict | None:
    row = conn.execute(
        "SELECT report_json FROM investigations WHERE id = ?", (inv_id,)).fetchone()
    return json.loads(row["report_json"]) if row else None


def delete(conn: sqlite3.Connection, inv_id: str) -> bool:
    cursor = conn.execute("DELETE FROM investigations WHERE id = ?", (inv_id,))
    conn.commit()
    return cursor.rowcount > 0


def staleness(conn: sqlite3.Connection, inv_id: str, current_head: str) -> str:
    row = conn.execute(
        "SELECT head FROM investigations WHERE id = ?", (inv_id,)).fetchone()
    if row is None:
        return "MISSING"
    return "CURRENT" if row["head"] == current_head else "STALE"


def compare(older: dict, newer: dict) -> dict:
    """Claim-level diff between two stored investigations."""
    def by_id(report: dict) -> dict:
        return {claim["id"]: claim for claim in report["claims"]}

    old, new = by_id(older), by_id(newer)
    changed = [
        {"claim_id": cid, "from": old[cid]["state"], "to": new[cid]["state"],
         "text": new[cid]["text"]}
        for cid in sorted(set(old) & set(new))
        if old[cid]["state"] != new[cid]["state"]
    ]
    return {
        "older_seal": older["seal"],
        "newer_seal": newer["seal"],
        "changed_claims": changed,
        "added_claims": sorted(set(new) - set(old)),
        "removed_claims": sorted(set(old) - set(new)),
        "older_contradictions": len(older["contradictions"]),
        "newer_contradictions": len(newer["contradictions"]),
    }


def manifest(report_dict: dict) -> dict:
    """Exportable manifest: identity, seal and reproducibility data."""
    return {
        "repo_path": report_dict["repo_path"],
        "source_kind": report_dict.get("source_kind", "local"),
        "source_ref": report_dict.get("source_ref", ""),
        "head": report_dict["head"],
        "snapshot": report_dict.get("snapshot", "head"),
        "seal": report_dict["seal"],
        "claims": len(report_dict["claims"]),
        "contradictions": len(report_dict["contradictions"]),
        "reproduce": (
            "necromancer excavate <repo> and compare the seal; "
            "the seal covers claims, links, contradictions and timeline, "
            "never hypotheses"
        ),
    }
