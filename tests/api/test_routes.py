import pytest
from fastapi.testclient import TestClient

from provider.main import create_app


@pytest.fixture()
def client():
    """Lifespan-aware client so services / admin service are initialized."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_chat_completions_requires_messages(client):
    """Chat completions must reject missing messages (422)."""
    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "test"}
    )
    assert response.status_code == 422


def test_chat_completions_requires_model(client):
    """Chat completions must reject missing model (422)."""
    response = client.post(
        "/api/v1/chat/completions",
        json={"messages": []}
    )
    assert response.status_code == 422


def test_admin_quota_endpoint_present(client):
    """The /api/admin/quota placeholder endpoint returns 200."""
    response = client.get("/api/admin/quota")
    assert response.status_code == 200
    data = response.json()
    assert "total_suppliers" in data
    assert "quota_status" in data
