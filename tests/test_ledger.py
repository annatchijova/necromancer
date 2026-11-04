from necromancer import ledger


def _filled(tmp_path):
    conn = ledger.connect(tmp_path / "ledger.db")
    ledger.append(conn, "ONE", {"a": 1}, ["a" * 64])
    ledger.append(conn, "TWO", {"b": 2}, ["b" * 64])
    ledger.append(conn, "THREE", {"c": 3}, ["c" * 64])
    return conn


def test_chain_verifies(tmp_path):
    conn = _filled(tmp_path)
    result = ledger.verify_chain(ledger.fetch_all(conn))
    assert result == {"linkage_ok": True, "integrity_ok": True, "issues": []}
    conn.close()


def test_tampered_payload_breaks_integrity(tmp_path):
    conn = _filled(tmp_path)
    conn.execute(
        "UPDATE ledger_entries SET payload_canonical = 'forged' WHERE id = 2"
    )
    conn.commit()
    result = ledger.verify_chain(ledger.fetch_all(conn))
    assert result["integrity_ok"] is False
    conn.close()


def test_deleted_entry_breaks_linkage(tmp_path):
    conn = _filled(tmp_path)
    conn.execute("DELETE FROM ledger_entries WHERE id = 2")
    conn.commit()
    result = ledger.verify_chain(ledger.fetch_all(conn))
    assert result["linkage_ok"] is False
    conn.close()
