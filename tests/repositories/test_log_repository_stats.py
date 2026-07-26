"""Tests for LogRepository stats-table methods and log retention cleanup."""
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from provider.repositories.log_repository import LogRepository

FMT = "%Y-%m-%d %H:%M:%S"


@pytest.fixture(autouse=True)
def _clean(database):
    """Isolate from rows leaked by other test modules (shared test DB file)."""
    with database.get_connection() as conn:
        conn.execute("DELETE FROM request_logs")
        conn.execute("DELETE FROM request_stats_minute")
    yield


def _ts(dt):
    return dt.strftime(FMT)


def _insert_stats(repo, db, ts, model="m1", account_id="a1", client_key="",
                  status_code=200, input_tokens=0, output_tokens=0,
                  latency_ms=None, cached_tokens=0):
    """Insert directly into request_stats_minute with explicit bucket."""
    repo.upsert_stats(
        timestamp=_ts(ts),
        model=model,
        account_id=account_id,
        client_key_name=client_key,
        status_code=status_code,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        cached_tokens=cached_tokens,
    )


# ── query_stats_summarize ──────────────────────────────────────────────────


def test_summarize_empty(database):
    repo = LogRepository(database)
    s = repo.query_stats_summarize("1990-01-01 00:00:00", "1990-01-01 00:05:00")
    assert s == {
        "total": 0, "success": 0, "total_tokens": 0, "avg_latency_ms": None,
    }


def test_summarize_basic(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    for i, sc in enumerate([200, 201, 429, 500]):
        _insert_stats(repo, database, base + timedelta(minutes=i),
                      status_code=sc, input_tokens=10, output_tokens=5)

    s = repo.query_stats_summarize(_ts(base), _ts(base + timedelta(minutes=3)))
    assert s["total"] == 4
    assert s["success"] == 2
    assert s["total_tokens"] == 60  # 4 * (10+5)


def test_summarize_latency_ignores_null(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1), latency_ms=100)
    _insert_stats(repo, database, base + timedelta(minutes=2), latency_ms=None)
    _insert_stats(repo, database, base + timedelta(minutes=3), latency_ms=200)

    s = repo.query_stats_summarize(_ts(base), _ts(base + timedelta(minutes=3)))
    assert s["avg_latency_ms"] == 150.0


# ── query_stats_aggregate (bucketed) ───────────────────────────────────────


def test_aggregate_bucketing(database):
    """Aggregation buckets at minute granularity (the precision of the stats table)."""
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    start = _ts(base)
    end = _ts(base + timedelta(minutes=29))

    # Four requests in the first 5-minute bucket [10:00, 10:05)
    for i in range(4):
        _insert_stats(repo, database, base + timedelta(minutes=i))
    # Two in the second bucket [10:05, 10:10)
    _insert_stats(repo, database, base + timedelta(minutes=5))
    _insert_stats(repo, database, base + timedelta(minutes=6))
    # One at the last bucket [10:25, 10:30)
    _insert_stats(repo, database, base + timedelta(minutes=25))
    # Out of bounds: one before start, one after end
    _insert_stats(repo, database, base - timedelta(minutes=1))
    _insert_stats(repo, database, base + timedelta(minutes=30))

    rows = repo.query_stats_aggregate(start, end, 300)  # 5-minute buckets
    by_bucket = {r["bucket_start"]: r["total"] for r in rows}

    first_bucket = _ts(base)
    assert by_bucket[first_bucket] == 4
    # All in-bounds rows: 4 + 2 + 1 = 7
    assert sum(by_bucket.values()) == 7


# ── query_stats_per_model ──────────────────────────────────────────────────


def test_per_model_ordering(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1), model="m1")
    _insert_stats(repo, database, base + timedelta(minutes=2), model="m1")
    _insert_stats(repo, database, base + timedelta(minutes=3), model="m2")

    rows = repo.query_stats_per_model(_ts(base), _ts(base + timedelta(minutes=30)))
    assert rows[0]["model"] == "m1"
    assert {r["model"]: r["total"] for r in rows} == {"m1": 2, "m2": 1}


def test_per_model_separates_same_name_across_accounts(database):
    """同名模型绑定到不同供应商(account_id)时，per-model 统计必须分两条，
    不能合并成一行。回归：此前仅按 model 分组，导致同名不同供应商被合并。"""
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    # 同一模型名 shared，来自两个不同账户（供应商）
    _insert_stats(repo, database, base + timedelta(minutes=1), model="shared", account_id="acc-a")
    _insert_stats(repo, database, base + timedelta(minutes=2), model="shared", account_id="acc-b")
    _insert_stats(repo, database, base + timedelta(minutes=3), model="shared", account_id="acc-b")

    rows = repo.query_stats_per_model(_ts(base), _ts(base + timedelta(minutes=30)))
    by_key = {(r["model"], r["account_id"]): r["total"] for r in rows}
    assert by_key == {("shared", "acc-a"): 1, ("shared", "acc-b"): 2}
    # 必须分两条，而非合并为一条 total=3
    assert len(rows) == 2


# ── query_stats_status_breakdown ───────────────────────────────────────────


def test_status_breakdown(database):
    """Status code breakdown reads from request_logs (the only table tracking
    per-status-code counts)."""
    from datetime import datetime as dt_cls

    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    rid = f"sb-{uuid.uuid4().hex[:12]}"
    repo.create(request_id=rid, model="m1")
    with repo.db.get_connection() as conn:
        conn.execute("UPDATE request_logs SET timestamp = ? WHERE request_id = ?",
                     (_ts(base), rid))

    rows = repo.query_stats_status_breakdown(_ts(base), _ts(base + timedelta(minutes=30)))
    assert rows == [{"status_code": None, "count": 1}]


# ── query_stats_by_models ──────────────────────────────────────────────────


def test_by_models_filters_and_aggregates(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1), model="m1",
                  input_tokens=10, output_tokens=5)
    _insert_stats(repo, database, base + timedelta(minutes=2), model="m1",
                  input_tokens=20, output_tokens=10)
    _insert_stats(repo, database, base + timedelta(minutes=3), model="m2",
                  input_tokens=30, output_tokens=15)

    rows = repo.query_stats_by_models(_ts(base), ["m1", "m2"])
    as_map = {r["model"]: r for r in rows}
    assert as_map["m1"]["input_tokens"] == 30
    assert as_map["m1"]["output_tokens"] == 15
    assert as_map["m2"]["input_tokens"] == 30


def test_by_models_empty_list(database):
    repo = LogRepository(database)
    assert repo.query_stats_by_models("1990-01-01 00:00:00", []) == []


# ── query_stats_client_key ─────────────────────────────────────────────────


def test_client_key_empty(database):
    repo = LogRepository(database)
    s = repo.query_stats_client_key("1990-01-01 00:00:00", "nonexistent")
    assert s["requests"] == 0


def test_client_key_enrichment(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1), client_key="k1",
                  input_tokens=10, output_tokens=5, cached_tokens=3)
    _insert_stats(repo, database, base + timedelta(minutes=2), client_key="k1",
                  input_tokens=20, output_tokens=10)
    _insert_stats(repo, database, base + timedelta(minutes=3), client_key="k2",
                  input_tokens=100)

    s = repo.query_stats_client_key(_ts(base), "k1")
    assert s["requests"] == 2
    assert s["input_tokens"] == 30
    assert s["output_tokens"] == 15
    assert s["cached_tokens"] == 3


# ── query_stats_key_summary / per_model ────────────────────────────────────


def test_key_summary(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1), client_key="k1",
                  status_code=200, input_tokens=10, output_tokens=5, latency_ms=100)
    _insert_stats(repo, database, base + timedelta(minutes=2), client_key="k1",
                  status_code=500, input_tokens=20, output_tokens=10, latency_ms=200)

    s = repo.query_stats_key_summary(_ts(base), "k1")
    assert s["total"] == 2
    assert s["success"] == 1
    assert s["input_tokens"] == 30
    assert s["output_tokens"] == 15
    assert s["latency_sum"] == 300
    assert s["latency_count"] == 2


def test_key_per_model(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1), model="m1",
                  client_key="k1", input_tokens=10, output_tokens=5)
    _insert_stats(repo, database, base + timedelta(minutes=2), model="m1",
                  client_key="k1", input_tokens=20, output_tokens=10)
    _insert_stats(repo, database, base + timedelta(minutes=3), model="m2",
                  client_key="k1", input_tokens=30, output_tokens=15)

    rows = repo.query_stats_key_per_model(_ts(base), "k1")
    as_map = {r["model"]: r for r in rows}
    assert as_map["m1"]["requests"] == 2
    assert as_map["m1"]["input_tokens"] == 30
    assert rows[0]["model"] == "m1"


# ── query_stats_global / heatmap / daily_trend / model_usage / supplier_daily
# ──────────────────────────────────────────────────────────────────────────────


def test_global_totals(database):
    repo = LogRepository(database)
    base = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
    _insert_stats(repo, database, base + timedelta(minutes=1),
                  input_tokens=10, output_tokens=5, cached_tokens=3)
    _insert_stats(repo, database, base + timedelta(minutes=2),
                  input_tokens=20, output_tokens=10)

    s = repo.query_stats_global(_ts(base), _ts(base + timedelta(minutes=3)))
    assert s["total"] == 2
    assert s["input_tokens"] == 30
    assert s["output_tokens"] == 15
    assert s["cached_tokens"] == 3


def test_heatmap(database):
    repo = LogRepository(database)
    base = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(hours=2)
    # Use fixed timestamps with known weekday/hour for deterministic checks.
    # 2024-01-01 is a Monday (weekday=0).
    _insert_stats(repo, database, datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc))
    _insert_stats(repo, database, datetime(2024, 1, 1, 10, 45, tzinfo=timezone.utc))
    _insert_stats(repo, database, datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc))

    rows = repo.query_stats_heatmap("2024-01-01 00:00:00", "2024-01-01 23:59:59")
    as_map = {(r["weekday"], r["hour"]): r["count"] for r in rows}
    assert (0, 10) in as_map
    assert as_map[(0, 10)] == 2
    assert as_map[(0, 11)] == 1


def test_daily_model_usage(database):
    """Daily model-level token breakdown for the stats table."""
    repo = LogRepository(database)
    _insert_stats(repo, database, datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                  model="m1", input_tokens=10, output_tokens=5)
    _insert_stats(repo, database, datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                  model="m2", input_tokens=20, output_tokens=10)
    _insert_stats(repo, database, datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                  model="m1", input_tokens=30, output_tokens=15)

    rows = repo.query_stats_daily_model_usage("2024-01-01 00:00:00", "2024-01-02 23:59:59")
    as_map = {(r["date"], r["model"]): r["tokens"] for r in rows}
    assert as_map[("2024-01-01", "m1")] == 15
    assert as_map[("2024-01-01", "m2")] == 30
    assert as_map[("2024-01-02", "m1")] == 45


def test_daily_trend(database):
    repo = LogRepository(database)
    _insert_stats(repo, database, datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                  input_tokens=10, output_tokens=5)
    _insert_stats(repo, database, datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                  input_tokens=20, output_tokens=10, cached_tokens=3)
    _insert_stats(repo, database, datetime(2024, 1, 2, 10, 0, tzinfo=timezone.utc),
                  input_tokens=100, output_tokens=50)

    rows = repo.query_stats_daily_trend("2024-01-01 00:00:00", "2024-01-02 23:59:59")
    by_date = {r["date"]: r for r in rows}
    assert by_date["2024-01-01"]["input_tokens"] == 30
    assert by_date["2024-01-01"]["output_tokens"] == 15
    assert by_date["2024-01-01"]["cached_tokens"] == 3
    assert by_date["2024-01-02"]["input_tokens"] == 100


def test_model_usage_and_supplier_daily(database):
    repo = LogRepository(database)
    _insert_stats(repo, database, datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                  model="m1", account_id="a1", input_tokens=10, output_tokens=5)
    _insert_stats(repo, database, datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                  model="m2", account_id="a1", input_tokens=20, output_tokens=10)
    _insert_stats(repo, database, datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc),
                  model="m1", account_id="a2", input_tokens=30, output_tokens=15)

    model_rows = repo.query_stats_model_usage("2024-01-01 00:00:00", "2024-01-01 23:59:59")
    model_map = {r["model"]: r["tokens"] for r in model_rows}
    assert model_map["m1"] == 60   # 15 + 45
    assert model_map["m2"] == 30   # 20 + 10

    sup_rows = repo.query_stats_supplier_daily("2024-01-01 00:00:00", "2024-01-01 23:59:59")
    sup_map = {(r["account_id"], r["date"]): r["tokens"] for r in sup_rows}
    assert sup_map[("a1", "2024-01-01")] == 45   # 15 + 30
    assert sup_map[("a2", "2024-01-01")] == 45   # 30 + 15


# ── query_stats_today_token_usage ──────────────────────────────────────────


def test_today_token_usage(database):
    repo = LogRepository(database)
    _insert_stats(repo, database, datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc),
                  model="m1", account_id="a1", input_tokens=10, output_tokens=5)
    _insert_stats(repo, database, datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
                  model="m1", account_id="a1", input_tokens=20, output_tokens=10)

    inp, out = repo.query_stats_today_token_usage(
        "a1", "m1", "2024-01-01 00:00:00", "2024-01-01 23:59:59",
    )
    assert inp == 30
    assert out == 15


# ── Log retention cleanup ──────────────────────────────────────────────────


def _insert_log(repo, db, ts, model="m1", status_code=200, latency_ms=100):
    """Insert a request_logs row with an explicit timestamp."""
    rid = f"wc-{uuid.uuid4().hex[:12]}"
    repo.create(request_id=rid, model=model, status_code=status_code,
                latency_ms=latency_ms)
    with db.get_connection() as conn:
        conn.execute("UPDATE request_logs SET timestamp = ? WHERE request_id = ?",
                     (_ts(ts), rid))
    return rid


def test_delete_older_than_removes_expired_rows(database):
    repo = LogRepository(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    old = now - timedelta(hours=2)
    recent = now - timedelta(minutes=30)

    _insert_log(repo, database, old, model="old-entry")
    _insert_log(repo, database, recent, model="recent-entry")

    deleted = repo.delete_older_than(_ts(now - timedelta(hours=1)))
    assert deleted == 1
    remaining, _ = repo.find_all(page=0, page_size=100)
    models = [r["model"] for r in remaining]
    assert "recent-entry" in models
    assert "old-entry" not in models


def test_delete_older_than_noop_when_nothing_expired(database):
    repo = LogRepository(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    _insert_log(repo, database, now - timedelta(minutes=2), model="entry")

    deleted = repo.delete_older_than(_ts(now - timedelta(minutes=5)))
    assert deleted == 0


def test_delete_older_than_removes_all_old_rows(database):
    repo = LogRepository(database)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    base = now - timedelta(days=1)

    for i in range(5):
        _insert_log(repo, database, base + timedelta(seconds=i), model=f"old-{i}")

    deleted = repo.delete_older_than(_ts(now - timedelta(hours=1)))
    assert deleted == 5
    remaining, _ = repo.find_all(page=0, page_size=100)
    assert len(remaining) == 0
