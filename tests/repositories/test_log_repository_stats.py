"""Tests for LogRepository window aggregation methods."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from provider.repositories.log_repository import LogRepository

FMT = "%Y-%m-%d %H:%M:%S"


@pytest.fixture(autouse=True)
def _clean_logs(database):
    """Isolate from rows leaked by other test modules (shared test DB file)."""
    with database.get_connection() as conn:
        conn.execute("DELETE FROM request_logs")
    yield


def _ts(dt):
    return dt.strftime(FMT)


def _insert(repo, db, ts, status_code=200, latency_ms=100, model="m1", actual=None):
    """Insert a log row with an explicit timestamp (create() relies on the column default)."""
    rid = f"wstats-{uuid.uuid4().hex[:12]}"
    repo.create(request_id=rid, model=model, actual_model_id=actual,
                status_code=status_code, latency_ms=latency_ms)
    with db.get_connection() as conn:
        conn.execute("UPDATE request_logs SET timestamp = ? WHERE request_id = ?",
                     (_ts(ts), rid))
    return rid


def test_empty_window(database):
    """A window with no rows — far in the past so leaked rows from other
    test modules (the API tests share this DB file) can't interfere."""
    repo = LogRepository(database)
    start, end = "1990-01-01 00:00:00", "1990-01-01 00:05:00"

    assert repo.summarize_window(start, end) == {
        "total": 0, "success": 0, "avg_latency_ms": None,
    }
    assert repo.aggregate_window(start, end, 10) == []
    assert repo.status_code_breakdown(start, end) == []
    assert repo.per_model_stats(start, end) == []


def test_aggregate_window_bucketing(database):
    repo = LogRepository(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    # Align base to a 10s bucket boundary so the expected buckets are exact.
    base = datetime.fromtimestamp((int(now.timestamp()) // 10) * 10,
                                  tz=timezone.utc) - timedelta(hours=2)
    start, end = base, base + timedelta(seconds=300)

    # Two rows in the first 10s bucket, one in the second, one exactly at end.
    _insert(repo, database, base + timedelta(seconds=0))
    _insert(repo, database, base + timedelta(seconds=9))
    _insert(repo, database, base + timedelta(seconds=10))
    _insert(repo, database, base + timedelta(seconds=300))
    # Out of bounds: 1s before start, 1s after end.
    _insert(repo, database, base - timedelta(seconds=1))
    _insert(repo, database, base + timedelta(seconds=301))

    rows = repo.aggregate_window(_ts(start), _ts(end), 10)
    by_bucket = {r["bucket_start"]: r["total"] for r in rows}

    first_bucket = _ts(datetime.fromtimestamp(
        (int(start.timestamp()) // 10) * 10, tz=timezone.utc))
    assert by_bucket[first_bucket] == 2
    # Boundary rows: start inclusive, end inclusive.
    assert sum(by_bucket.values()) == 4


def test_success_classification(database):
    repo = LogRepository(database)
    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    start, end = _ts(base), _ts(base + timedelta(seconds=300))

    for i, sc in enumerate([200, 201, 301, 429, 500, None]):
        _insert(repo, database, base + timedelta(seconds=i), status_code=sc)

    summary = repo.summarize_window(start, end)
    assert summary["total"] == 6          # NULL status still counts as a request
    assert summary["success"] == 3        # 200 / 201 / 301


def test_avg_latency_ignores_null(database):
    repo = LogRepository(database)
    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    start, end = _ts(base), _ts(base + timedelta(seconds=300))

    _insert(repo, database, base + timedelta(seconds=1), latency_ms=100)
    _insert(repo, database, base + timedelta(seconds=2), latency_ms=None)
    _insert(repo, database, base + timedelta(seconds=3), latency_ms=200)

    assert repo.summarize_window(start, end)["avg_latency_ms"] == 150


def test_status_code_breakdown(database):
    repo = LogRepository(database)
    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    start, end = _ts(base), _ts(base + timedelta(seconds=300))

    for i, sc in enumerate([200, 200, 200, 429, 500, None]):
        _insert(repo, database, base + timedelta(seconds=i), status_code=sc)

    rows = repo.status_code_breakdown(start, end)
    assert rows[0] == {"status_code": 200, "count": 3}  # ordered by count desc
    as_map = {r["status_code"]: r["count"] for r in rows}
    assert as_map == {200: 3, 429: 1, 500: 1, None: 1}


def test_per_model_stats_coalesce(database):
    repo = LogRepository(database)
    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    start, end = _ts(base), _ts(base + timedelta(seconds=300))

    # Alias a1 resolves to actual model m1 → groups under m1.
    _insert(repo, database, base + timedelta(seconds=1), model="a1", actual="m1")
    _insert(repo, database, base + timedelta(seconds=2), model="a1", actual="m1",
            status_code=500)
    # No actual model → groups under the alias itself.
    _insert(repo, database, base + timedelta(seconds=3), model="a2", actual=None)

    rows = repo.per_model_stats(start, end)
    as_map = {r["model"]: r for r in rows}
    assert as_map["m1"]["total"] == 2
    assert as_map["m1"]["success"] == 1
    assert as_map["a2"]["total"] == 1
    assert rows[0]["model"] == "m1"  # ordered by total desc
