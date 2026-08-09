"""Tests for supplier models API endpoints."""
import datetime
import pytest
from fastapi.testclient import TestClient

from provider.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _tid(suffix: str) -> str:
    return f"sm{datetime.datetime.now().strftime('%H%M%S%f')}-{suffix}"


def _create_supplier(client):
    name = _tid("sup")
    r = client.post("/api/admin/suppliers", json={
        "name": name, "api_keys": ["ms-test-key"],
        "base_url": "https://api.modelscope.test/v1",
    })
    return r.json()


def test_list_supplier_models_empty(client):
    supplier = _create_supplier(client)
    r = client.get(f"/api/admin/suppliers/{supplier['id']}/models")
    assert r.status_code == 200
    assert r.json() == []


def test_create_supplier_model(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max",
        "model_type": "text",
        "context_length": 32768,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["model_name"] == "qwen-max"
    assert data["model_type"] == "text"
    assert data["context_length"] == 32768


def test_create_supplier_model_duplicate_409(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max", "model_type": "text",
    })
    r = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max", "model_type": "text",
    })
    assert r.status_code == 409


def test_create_supplier_model_default_type(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "glm-4",
    })
    assert r.status_code == 200
    assert r.json()["model_type"] == "text"


def test_bulk_set_supplier_models(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.put(f"/api/admin/suppliers/{sid}/models/bulk", json={
        "models": [
            {"model_name": "qwen-max", "model_type": "text", "context_length": 32768},
            {"model_name": "qwen-vl", "model_type": "image", "context_length": 4096},
            {"model_name": "code-geex", "model_type": "code"},
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    names = {m["model_name"] for m in data}
    assert names == {"qwen-max", "qwen-vl", "code-geex"}


def test_delete_supplier_model(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    created = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "glm-4", "model_type": "text",
    }).json()
    mid = created["id"]
    r = client.delete(f"/api/admin/suppliers/{sid}/models/{mid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert client.get(f"/api/admin/suppliers/{sid}/models").json() == []


def test_delete_supplier_model_not_found(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.delete(f"/api/admin/suppliers/{sid}/models/99999")
    assert r.status_code == 404


def test_delete_supplier_cascades_models(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max", "model_type": "text",
    })
    client.delete(f"/api/admin/suppliers/{sid}")
    assert client.get(f"/api/admin/suppliers/{sid}/models").json() == []
