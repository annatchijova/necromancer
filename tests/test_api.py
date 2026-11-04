from fastapi.testclient import TestClient

from necromancer.api import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "PASS"


def test_excavate_fixture_a(synthetic):
    response = client.post("/excavate", json={"path": str(synthetic["a"])})
    assert response.status_code == 200
    body = response.json()
    assert body["seal"]
    states = {claim["state"] for claim in body["claims"]}
    assert "CONTRADICTED" in states
    for claim in body["claims"]:
        assert claim["origin"] and claim["scope"] and claim["falsifier"]


def test_excavate_rejects_non_repo(tmp_path):
    response = client.post("/excavate", json={"path": str(tmp_path)})
    assert response.status_code == 400
