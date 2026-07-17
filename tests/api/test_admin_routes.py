"""Tests for admin API routes (management panel backends)."""
import datetime
import pytest
from fastapi.testclient import TestClient

from provider.main import create_app


@pytest.fixture()
def client():
    """TestClient with lifespan triggered so admin service is initialized."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def _tid(suffix: str) -> str:
    """Create a per-run unique name suffix to avoid collisions on the shared DB."""
    now = datetime.datetime.now().strftime("%H%M%S%f")
    return f"adm{now}-{suffix}"


def _list(client):
    return client.get("/api/admin/suppliers").json()


def _create(client, name="test-supplier", api_key="ms-test-key",
            base_url="https://api.modelscope.test/v1"):
    return client.post("/api/admin/suppliers", json={
        "name": name, "api_key": api_key,
        "base_url": base_url,
    }).json()


# ── Suppliers ───────────────────────────────────────────────────────────────

def test_list_suppliers(client):
    data = _list(client)
    assert isinstance(data, list)


def test_create_supplier(client):
    name = _tid("create")
    r = client.post("/api/admin/suppliers", json={
        "name": name, "api_key": "ms-test-key",
        "base_url": "https://api.modelscope.test/v1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == name
    assert len(body["account_id"]) == 32  # UUID hex
    assert body["status"] == "active"
    assert "id" in body


def test_create_supplier_duplicate_name_returns_409(client):
    name = _tid("dup")
    payload = {
        "name": name, "api_key": "k1", "base_url": "https://u/v1",
    }
    client.post("/api/admin/suppliers", json=payload)
    r = client.post("/api/admin/suppliers", json=payload)
    assert r.status_code == 409


def test_update_supplier(client):
    created = _create(client, _tid("upd"), "k1", "https://u/v1")
    iid = created["id"]
    r = client.put(f"/api/admin/suppliers/{iid}", json={"status": "disabled"})
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"


def test_update_supplier_not_found(client):
    r = client.put("/api/admin/suppliers/99999", json={"status": "active"})
    assert r.status_code == 404


def test_toggle_supplier(client):
    created = _create(client, _tid("toggle"))
    # Fresh supplier is "active"; toggle -> "disabled"
    r = client.patch(f"/api/admin/suppliers/{created['id']}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    # Toggle back -> "active"
    r2 = client.patch(f"/api/admin/suppliers/{created['id']}/status")
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"


def test_toggle_supplier_not_found(client):
    r = client.patch("/api/admin/suppliers/99999/status")
    assert r.status_code == 404


def test_delete_supplier(client):
    before = len(_list(client))
    created = _create(client, _tid("del"), "k3", "https://u/v1")
    r = client.delete(f"/api/admin/suppliers/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert len(_list(client)) == before


def test_delete_supplier_not_found(client):
    r = client.delete("/api/admin/suppliers/99999")
    assert r.status_code == 404


# ── Mappings ────────────────────────────────────────────────────────────────

def test_list_mappings(client):
    data = client.get("/api/admin/mappings").json()
    assert isinstance(data, list)


def test_bulk_update_mappings(client):
    aid = _tid("map")
    payload = {"mappings": {
        aid: "my-actual-model",
    }}
    r = client.put("/api/admin/mappings/bulk", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert any(m["alias_name"] == aid for m in data)


def test_delete_mapping(client):
    aid = _tid("delmap")
    client.put("/api/admin/mappings/bulk", json={
        "mappings": {aid: "some-model"}
    })
    r = client.delete(f"/api/admin/mappings/{aid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


# ── Config ──────────────────────────────────────────────────────────────────

def test_get_config(client):
    data = client.get("/api/admin/config").json()
    assert isinstance(data, dict)
    assert "log_level" in data
    assert "value" in data["log_level"]


def test_update_config(client):
    r = client.put("/api/admin/config", json={"config": {"log_level": "DEBUG"}})
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["log_level"]["value"] == "DEBUG"


# ── Suppliers (detail) ──────────────────────────────────────────────────────

def test_get_supplier(client):
    created = _create(client, _tid("getone"))
    iid = created["id"]
    r = client.get(f"/api/admin/suppliers/{iid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == iid
    assert body["quota_remaining"] == 0
    assert body["quota_limit"] == 0


def test_get_supplier_not_found(client):
    r = client.get("/api/admin/suppliers/99999")
    assert r.status_code == 404


# ── Logs ────────────────────────────────────────────────────────────────────

def test_list_logs_shape(client):
    r = client.get("/api/admin/logs")
    assert r.status_code == 200
    data = r.json()
    for key in ("records", "total", "page", "page_size"):
        assert key in data


def test_list_logs_with_filter_params(client):
    r = client.get("/api/admin/logs?page=0&page_size=10&status_code=429")
    assert r.status_code == 200
    assert "records" in r.json() and "total" in r.json()


def test_get_log_detail_not_found(client):
    r = client.get("/api/admin/logs/99999")
    assert r.status_code == 404


# ── Stats ───────────────────────────────────────────────────────────────────

def test_get_stats(client):
    r = client.get("/api/admin/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("heatmap", "daily_tokens", "model_usage", "total_requests"):
        assert key in data


def test_get_stats_days_param(client):
    r = client.get("/api/admin/stats?days=7")
    assert r.status_code == 200


# ── Alerts ──────────────────────────────────────────────────────────────────

def test_list_alerts(client):
    r = client.get("/api/admin/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_alerts_days_param(client):
    r = client.get("/api/admin/alerts?days=14")
    assert r.status_code == 200
