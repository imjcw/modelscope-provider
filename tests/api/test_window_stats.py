"""Tests for GET /api/admin/stats/window (dashboard live panel endpoint)."""
import datetime
import os
import uuid

import pytest
from fastapi.testclient import TestClient

from provider.core.database import DatabaseManager
from provider.main import create_app
from provider.repositories.log_repository import LogRepository

FMT = "%Y-%m-%d %H:%M:%S"


@pytest.fixture()
def client():
    """TestClient with lifespan triggered so admin service is initialized."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def _tid(suffix: str) -> str:
    """Per-run unique suffix — the API tests share one test DB."""
    return f"ws{datetime.datetime.now().strftime('%H%M%S%f')}-{suffix}"


def _insert_log(ts, status_code=200, model="m1", actual=None):
    """Insert directly into the shared test DB (same URL the app lifespan used)."""
    db = DatabaseManager(os.environ["DATABASE_URL"])
    repo = LogRepository(db)
    rid = f"apws-{uuid.uuid4().hex[:12]}"
    repo.create(request_id=rid, model=model, actual_model_id=actual,
                status_code=status_code, latency_ms=120)
    with db.get_connection() as conn:
        conn.execute("UPDATE request_logs SET timestamp = ? WHERE request_id = ?",
                     (ts.strftime(FMT), rid))


def test_window_stats_shape(client):
    r = client.get("/api/admin/stats/window")
    assert r.status_code == 200
    data = r.json()

    assert set(data.keys()) == {
        "window_seconds", "bucket_seconds", "start", "end",
        "kpi", "prev", "series", "status_codes", "models",
    }
    assert data["window_seconds"] == 300
    assert data["bucket_seconds"] == 10
    assert 30 <= len(data["series"]) <= 31

    kpi = data["kpi"]
    assert set(kpi.keys()) == {"total", "success", "failed", "success_rate",
                               "qps", "avg_latency_ms", "delta"}
    assert set(kpi["delta"].keys()) == {"total_pct", "success_rate_pp", "avg_latency_pct"}

    cell = data["series"][0]
    assert set(cell.keys()) == {"t", "total", "success", "qps",
                                "success_rate", "avg_latency_ms"}


def test_window_bucket_mapping(client):
    assert client.get("/api/admin/stats/window?seconds=300").json()["bucket_seconds"] == 10
    assert client.get("/api/admin/stats/window?seconds=3600").json()["bucket_seconds"] == 120
    assert client.get("/api/admin/stats/window?seconds=86400").json()["bucket_seconds"] == 3600
    # Out-of-range values are clamped, not rejected.
    assert client.get("/api/admin/stats/window?seconds=5").json()["window_seconds"] == 60


def test_window_counts_inserted_logs(client):
    model = _tid("model")
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    _insert_log(now - datetime.timedelta(seconds=60), status_code=200, model="alias", actual=model)
    _insert_log(now - datetime.timedelta(seconds=90), status_code=200, model="alias", actual=model)
    _insert_log(now - datetime.timedelta(seconds=120), status_code=500, model="alias", actual=model)

    data = client.get("/api/admin/stats/window?seconds=300").json()
    matches = [m for m in data["models"] if m["model"] == model]
    assert len(matches) == 1
    assert matches[0]["total"] == 3
    assert matches[0]["success"] == 2

    assert data["kpi"]["total"] >= 3
    assert str(500) in data["status_codes"]
