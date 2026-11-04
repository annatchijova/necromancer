import pytest
from fastapi.testclient import TestClient

from necromancer.api import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path, monkeypatch):
    monkeypatch.setenv("NECROMANCER_DB", str(tmp_path / "inv.db"))


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "PASS"


def test_excavate_fixture_a_legacy_path(synthetic):
    response = client.post("/excavate", json={"path": str(synthetic["a"])})
    assert response.status_code == 200
    body = response.json()
    assert body["seal"]
    states = {claim["state"] for claim in body["claims"]}
    assert "CONTRADICTED" in states
    for claim in body["claims"]:
        assert claim["origin"] and claim["scope"] and claim["falsifier"]
        assert claim["line"] is None or claim["line"] >= 1


def test_excavate_rejects_non_repo(tmp_path):
    response = client.post("/excavate", json={"path": str(tmp_path)})
    assert response.status_code == 400


def test_investigation_persistence_flow(synthetic):
    created = client.post(
        "/investigations", json={"source": str(synthetic["b"]), "save": True})
    assert created.status_code == 200
    inv_id = created.json()["investigation_id"]
    listed = client.get("/investigations").json()["investigations"]
    assert any(item["id"] == inv_id for item in listed)
    reopened = client.get(f"/investigations/{inv_id}")
    assert reopened.status_code == 200
    assert reopened.json()["seal"] == created.json()["seal"]
    assert reopened.json()["workspace_status"] in ("CURRENT", "STALE", "UNKNOWN")
    manifest = client.get(f"/investigations/{inv_id}/manifest")
    assert manifest.json()["seal"] == created.json()["seal"]
    compared = client.post(
        "/compare", json={"older_id": inv_id, "newer_id": inv_id})
    assert compared.json()["changed_claims"] == []
    assert client.delete(f"/investigations/{inv_id}").status_code == 200
    assert client.get(f"/investigations/{inv_id}").status_code == 404


def test_synthetic_fixture_is_labeled():
    listing = client.get("/fixtures").json()
    assert all(item["synthetic"] for item in listing["fixtures"])
    body = client.post("/fixtures/c").json()
    assert body["source_kind"] == "synthetic"
    states = {claim["state"] for claim in body["claims"]}
    assert "CONTRADICTED" in states


def test_github_acquisition_rejects_evil_url():
    response = client.post(
        "/investigations", json={"source": "https://evil.example/a/b"})
    assert response.status_code == 400
