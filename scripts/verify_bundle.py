#!/usr/bin/env python3
"""Independent NECROMANCER bundle verifier. Stdlib only.

Checks a report JSON for provenance completeness and, when given a ledger
database, recomputes the hash chain without importing producer code.
It verifies evidence integrity claims, never factual truth.

Usage: python3 scripts/verify_bundle.py report.json [ledger.db]
Exit 0 when every check passes, 1 otherwise.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
from pathlib import Path


def check_report(report: dict) -> list[str]:
    issues: list[str] = []
    seal = report.get("seal", "")
    if len(seal) != 64 or any(c not in "0123456789abcdef" for c in seal):
        issues.append("seal is not a SHA-256 hex digest")
    for claim in report.get("claims", []):
        for field in ("origin", "scope", "falsifier", "state"):
            if not claim.get(field):
                issues.append(f"claim {claim.get('id')}: missing {field}")
    for hyp in report.get("hypotheses_not_facts", []):
        if hyp.get("provenance") != "HYPOTHESIS":
            issues.append(f"hypothesis {hyp.get('id')}: provenance is not HYPOTHESIS")
    states = {claim.get("state") for claim in report.get("claims", [])}
    if "VERIFIED" in states:
        issues.append("note: VERIFIED present; this verifier cannot confirm trusted execution evidence")
    return issues


def check_ledger(db_path: Path) -> list[str]:
    issues: list[str] = []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("SELECT * FROM ledger_entries ORDER BY id ASC").fetchall()
    except sqlite3.Error as error:
        return [f"ledger unreadable: {error}"]
    finally:
        conn.close()
    prev = "0" * 64
    for row in rows:
        if row["prev_hash"] != prev:
            issues.append(f"entry {row['id']}: linkage broken")
        material = f"{row['payload_canonical']}|{row['prev_hash']}|{row['ts_iso']}"
        if hashlib.sha256(material.encode("utf-8")).hexdigest() != row["audit_hash"]:
            issues.append(f"entry {row['id']}: integrity broken")
        prev = row["audit_hash"]
    return issues


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: verify_bundle.py report.json [ledger.db]")
        return 2
    report = json.loads(Path(argv[1]).read_text(encoding="utf-8"))
    issues = check_report(report)
    if len(argv) > 2:
        issues += check_ledger(Path(argv[2]))
    for issue in issues:
        print(f"FAIL: {issue}")
    print("PASS: bundle checks" if not issues else "FAIL: bundle checks")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
