"""Append-only, tamper-evident evidence ledger (SQLite, stdlib only).

Each entry stores prev_hash and audit_hash where
audit_hash = sha256(canonical_payload | prev_hash | ts_iso). The timestamp
is captured once and stored, so the chain can always be recomputed from
persisted data. Verification reports linkage and integrity separately.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from .canonicalize import canonical_text

GENESIS = "0" * 64

_SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts_iso TEXT NOT NULL,
  op TEXT NOT NULL,
  payload_canonical TEXT NOT NULL,
  content_hashes TEXT NOT NULL,
  prev_hash TEXT NOT NULL,
  audit_hash TEXT NOT NULL
)
"""


def connect(path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def _audit_hash(payload_canonical: str, prev_hash: str, ts_iso: str) -> str:
    material = f"{payload_canonical}|{prev_hash}|{ts_iso}"
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def _last_hash(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT audit_hash FROM ledger_entries ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["audit_hash"] if row else GENESIS


def _tail_broken(conn: sqlite3.Connection, window: int = 5) -> bool:
    rows = conn.execute(
        "SELECT * FROM ledger_entries ORDER BY id DESC LIMIT ?", (window,)
    ).fetchall()
    rows = list(reversed(rows))
    for prev, cur in zip(rows, rows[1:]):
        if cur["prev_hash"] != prev["audit_hash"]:
            return True
    for row in rows:
        if _audit_hash(row["payload_canonical"], row["prev_hash"], row["ts_iso"]) != row["audit_hash"]:
            return True
    return False


def append(conn: sqlite3.Connection, op: str, body: dict, content_hashes: list[str]) -> tuple[int, str]:
    """Append one entry, continuing the single chain. Warns on a broken tail."""
    if _tail_broken(conn):
        print("WARN: existing ledger tail is broken; appending without laundering it", file=sys.stderr)
    ts_iso = datetime.now(timezone.utc).isoformat()
    payload_canonical = canonical_text({"op": op, "body": body})
    prev_hash = _last_hash(conn)
    audit_hash = _audit_hash(payload_canonical, prev_hash, ts_iso)
    cursor = conn.execute(
        "INSERT INTO ledger_entries (ts_iso, op, payload_canonical, content_hashes, prev_hash, audit_hash)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (ts_iso, op, payload_canonical, json.dumps(sorted(content_hashes)), prev_hash, audit_hash),
    )
    conn.commit()
    return int(cursor.lastrowid), audit_hash


def fetch_all(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM ledger_entries ORDER BY id ASC").fetchall()


def verify_chain(rows: list[sqlite3.Row]) -> dict:
    """Check linkage and integrity as two independent properties."""
    issues: list[str] = []
    linkage_ok = True
    integrity_ok = True
    prev_hash = GENESIS
    for row in rows:
        if row["prev_hash"] != prev_hash:
            linkage_ok = False
            issues.append(f"entry {row['id']}: prev_hash does not match previous audit_hash")
        if _audit_hash(row["payload_canonical"], row["prev_hash"], row["ts_iso"]) != row["audit_hash"]:
            integrity_ok = False
            issues.append(f"entry {row['id']}: audit_hash does not recompute from stored fields")
        prev_hash = row["audit_hash"]
    return {"linkage_ok": linkage_ok, "integrity_ok": integrity_ok, "issues": issues}
