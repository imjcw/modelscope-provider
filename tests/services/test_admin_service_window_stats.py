"""Tests for AdminService.get_window_stats (dashboard windowed aggregation)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from provider.repositories.account_repository import AccountRepository
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.log_repository import LogRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.services.admin_service import AdminService

FMT = "%Y-%m-%d %H:%M:%S"


@pytest.fixture(autouse=True)
def _clean_logs(database):
    """Isolate from rows leaked by other test modules (shared test DB file)."""
    with database.get_connection() as conn:
        conn.execute("DELETE FROM request_logs")
    yield


def _make_service(db):
    return AdminService(
        AccountRepository(db), MappingRepository(db),
        ConfigRepository(db), LogRepository(db),
    )


def _insert(db, ts, status_code=200, latency_ms=100, model="m1", actual=None):
    repo = LogRepository(db)
    rid = f"wwin-{uuid.uuid4().hex[:12]}"
    repo.create(request_id=rid, model=model, actual_model_id=actual,
                status_code=status_code, latency_ms=latency_ms)
    with db.get_connection() as conn:
        conn.execute("UPDATE request_logs SET timestamp = ? WHERE request_id = ?",
                     (ts.strftime(FMT), rid))
    return rid


def test_empty_database_returns_flat_grid(database):
    svc = _make_service(database)
    out = svc.get_window_stats(300)

    assert out["window_seconds"] == 300
    assert out["bucket_seconds"] == 10
    n = len(out["series"])
    assert 30 <= n <= 31  # epoch-aligned grid may carry one partial trailing bucket
    assert all(c["total"] == 0 and c["qps"] == 0.0 and c["success_rate"] is None
               for c in out["series"])
    kpi = out["kpi"]
    assert kpi["total"] == 0 and kpi["failed"] == 0
    assert kpi["success_rate"] is None and kpi["avg_latency_ms"] is None
    assert kpi["delta"] == {"total_pct": None, "success_rate_pp": None,
                            "avg_latency_pct": None}
    assert out["status_codes"] == {}
    assert out["models"] == []


def test_delta_across_window_boundary(database):
    svc = _make_service(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # 3 requests in the current 5-minute window, 2 in the previous one,
    # 1 even older (must be ignored).
    for i in range(3):
        _insert(database, now - timedelta(seconds=60 + i * 10))
    for i in range(2):
        _insert(database, now - timedelta(seconds=400 + i * 10))
    _insert(database, now - timedelta(seconds=700))

    out = svc.get_window_stats(300)
    assert out["kpi"]["total"] == 3
    assert out["prev"]["total"] == 2
    assert out["kpi"]["delta"]["total_pct"] == 50.0  # (3 - 2) / 2 * 100


def test_status_and_latency_math(database):
    svc = _make_service(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    rows = [(200, 100), (200, 200), (429, 50), (500, None), (None, 300)]
    for i, (sc, lat) in enumerate(rows):
        _insert(database, now - timedelta(seconds=30 + i), status_code=sc, latency_ms=lat)

    kpi = svc.get_window_stats(300)["kpi"]
    assert kpi["total"] == 5
    assert kpi["success"] == 2
    assert kpi["failed"] == 3
    assert kpi["success_rate"] == 40.0
    # AVG over non-NULL latencies: (100 + 200 + 50 + 300) / 4
    assert kpi["avg_latency_ms"] == 162  # round(162.5) → banker's rounding → 162


def test_single_row_lands_in_correct_bucket(database):
    svc = _make_service(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ts = now - timedelta(seconds=150)
    _insert(database, ts)

    out = svc.get_window_stats(300)
    nonzero = [c for c in out["series"] if c["total"] > 0]
    assert len(nonzero) == 1

    bucket_epoch = (int(ts.timestamp()) // 10) * 10
    expected_t = datetime.fromtimestamp(bucket_epoch, tz=timezone.utc).strftime(FMT)
    assert nonzero[0]["t"] == expected_t
    assert nonzero[0]["success_rate"] == 100.0


def test_window_and_bucket_clamping(database):
    svc = _make_service(database)

    assert svc.get_window_stats(10)["window_seconds"] == 60
    assert svc.get_window_stats(10 ** 6)["window_seconds"] == 86400
    assert svc.get_window_stats(300)["bucket_seconds"] == 10
    assert svc.get_window_stats(3600)["bucket_seconds"] == 120
    assert svc.get_window_stats(86400)["bucket_seconds"] == 3600

    out = svc.get_window_stats(3600)
    n = len(out["series"])
    assert 30 <= n <= 31  # 3600 / 120


def test_models_grouped_by_actual_model(database):
    svc = _make_service(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)

    _insert(database, now - timedelta(seconds=20), model="alias", actual="real-1")
    _insert(database, now - timedelta(seconds=30), model="alias", actual="real-1",
            status_code=500)
    _insert(database, now - timedelta(seconds=40), model="plain", actual=None)

    models = svc.get_window_stats(300)["models"]
    as_map = {m["model"]: m for m in models}
    assert as_map["real-1"]["total"] == 2
    assert as_map["real-1"]["success"] == 1
    assert as_map["real-1"]["success_rate"] == 50.0
    assert as_map["plain"]["total"] == 1
