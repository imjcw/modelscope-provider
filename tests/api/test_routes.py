import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from provider.main import create_app


def test_health_check():
    """Test health check endpoint."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
    assert response.json()["version"] == "0.1.0"


def test_chat_completions_returns_200():
    """Test chat completions endpoint returns valid response."""
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/v1/chat/completions",
        json={"model": "test", "messages": []}
    )

    # Should return 200 with placeholder response
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "choices" in data
    assert data["choices"][0]["message"]["role"] == "assistant"


def test_admin_quota_returns_200():
    """Test admin quota endpoint returns valid response."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/admin/quota")

    # Should return 200 with placeholder response
    assert response.status_code == 200
    data = response.json()
    assert "total_accounts" in data
    assert "quota_status" in data
