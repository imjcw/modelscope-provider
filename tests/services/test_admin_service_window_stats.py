"""Tests for AdminService.get_window_stats (dashboard windowed aggregation)."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from core.timezone import TZ

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
        conn.execute("DELETE FROM request_stats_minute")
    yield


def _make_service(db):
    return AdminService(
        AccountRepository(db), MappingRepository(db),
        ConfigRepository(db), LogRepository(db),
    )


def _insert(db, ts, status_code=200, latency_ms=100, model="m1", actual=None,
            input_tokens=0, output_tokens=0, client_key=""):
    repo = LogRepository(db)
    rid = f"wwin-{uuid.uuid4().hex[:12]}"
    ts_str = ts.strftime(FMT)
    # Update timestamp for the log row (create() uses column default).
    repo.create(request_id=rid, model=model, actual_model_id=actual,
                status_code=status_code, latency_ms=latency_ms,
                input_tokens=input_tokens, output_tokens=output_tokens)
    with db.get_connection() as conn:
        conn.execute("UPDATE request_logs SET timestamp = ? WHERE request_id = ?",
                     (ts_str, rid))
    # Also populate the minute-level stats table so window stats queries find the data.
    repo.upsert_stats(
        timestamp=ts_str,
        model=actual or model,
        account_id="test-account",
        client_key_name=client_key,
        status_code=status_code,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cached_tokens=0,
    )
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
    assert kpi["total"] == 0 and kpi["failed"] == 0 and kpi["total_tokens"] == 0
    assert kpi["success_rate"] is None and kpi["avg_latency_ms"] is None
    assert kpi["delta"] == {"total_pct": None, "total_tokens_pct": None, "success_rate_pp": None,
                            "avg_latency_pct": None}
    assert out["status_codes"] == {}
    assert out["models"] == []


def test_delta_across_window_boundary(database):
    svc = _make_service(database)
    now = datetime.now(TZ).replace(microsecond=0)

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
    now = datetime.now(TZ).replace(microsecond=0)

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


def test_total_tokens_aggregation(database):
    svc = _make_service(database)
    now = datetime.now(TZ).replace(microsecond=0)

    # 2 requests with tokens, 1 without
    _insert(database, now - timedelta(seconds=30), input_tokens=100, output_tokens=50)
    _insert(database, now - timedelta(seconds=60), input_tokens=200, output_tokens=75)
    _insert(database, now - timedelta(seconds=90), status_code=500)

    kpi = svc.get_window_stats(300)["kpi"]
    assert kpi["total_tokens"] == 425  # 100+50 + 200+75
    assert kpi["delta"]["total_tokens_pct"] is None  # no prev window data


def test_total_tokens_in_series(database):
    svc = _make_service(database)
    now = datetime.now(TZ).replace(microsecond=0)

    _insert(database, now - timedelta(seconds=30), input_tokens=150, output_tokens=60)

    out = svc.get_window_stats(300)
    nonzero = [c for c in out["series"] if c["total_tokens"] > 0]
    assert len(nonzero) >= 1
    assert nonzero[0]["total_tokens"] == 210  # 150+60


def test_single_row_lands_in_correct_bucket(database):
    """Rows stored at minute granularity in request_stats_minute; bucket
    alignment must respect that (minute, not sub-minute)."""
    svc = _make_service(database)
    now = datetime.now(TZ).replace(microsecond=0)
    ts = now - timedelta(seconds=150)
    _insert(database, ts)

    out = svc.get_window_stats(300)
    nonzero = [c for c in out["series"] if c["total"] > 0]
    assert len(nonzero) == 1

    # Stats table stores minute-aligned buckets.
    bucket_minute = ts.replace(second=0, microsecond=0)
    expected_t = bucket_minute.strftime(FMT)
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
    now = datetime.now(TZ).replace(microsecond=0)

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


def test_window_stats_normalizes_mixed_timestamp_formats(database):
    """Regression: stats written with ``T`` separators, UTC offsets or naive
    timestamps must still be readable by ``get_window_stats``. The bucket key
    must be normalized to Shanghai-local, space-separated minute format so the
    query side (also Shanghai-local) can match it.
    """
    svc = _make_service(database)
    now = datetime.now(TZ).replace(microsecond=0)
    base = now - timedelta(seconds=30)
    repo = LogRepository(database)

    ts_shanghai = base.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    ts_utc = base.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    ts_naive_t = base.strftime("%Y-%m-%dT%H:%M:%S")

    for ts in (ts_shanghai, ts_utc, ts_naive_t):
        repo.upsert_stats(
            timestamp=ts, model="shared-model", account_id="acc-1",
            status_code=200, input_tokens=0, output_tokens=0, latency_ms=10,
        )

    out = svc.get_window_stats(300)
    models = {m["model"]: m for m in out["models"]}
    assert models["shared-model"]["total"] == 3
    assert out["kpi"]["total"] == 3
