"""Tests for migration 030 (fold cache tokens back into input_tokens)."""
import sqlite3

import pytest

from provider.core.database import DatabaseManager
from provider.core.migrations import get_all_migrations


def _run_030(conn):
    return next(m for m in get_all_migrations() if m.version == 30).up(conn)


def _logs_table(conn, with_creation: bool = True):
    creation = ",\n                prompt_partial_cached INTEGER DEFAULT 0" if with_creation else ""
    conn.execute(f"""
        CREATE TABLE request_logs (
            request_id TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0{creation}
        )""")


def _stats_table(conn):
    conn.execute("""
        CREATE TABLE request_stats_minute (
            bucket TEXT NOT NULL, model TEXT NOT NULL DEFAULT '',
            input_tokens INTEGER NOT NULL DEFAULT 0,
            output_tokens INTEGER NOT NULL DEFAULT 0,
            cached_tokens INTEGER NOT NULL DEFAULT 0
        )""")


@pytest.fixture
def db(tmp_path):
    return DatabaseManager(f"sqlite:///{tmp_path}/mig030_test.db")


class TestMigration030:
    def test_folds_cache_back_into_exclusive_rows_only(self, db):
        db.initialize_tables()
        with db.get_connection() as conn:
            # DeepSeek 口径：缓存报在 input 之外 → 需要修补
            conn.execute(
                "INSERT INTO request_logs "
                "(request_id, model, input_tokens, cached_tokens) "
                "VALUES ('exclusive', 'm', 305, 221952)")
            # 商汤/智谱 口径：缓存已含在 input 里 → 不能动
            conn.execute(
                "INSERT INTO request_logs "
                "(request_id, model, input_tokens, cached_tokens) "
                "VALUES ('inclusive', 'm', 89179, 88960)")
            # 分钟表：cached_tokens 在写入时就已折入 creation
            conn.execute(
                "INSERT INTO request_stats_minute "
                "(bucket, model, input_tokens, cached_tokens) "
                "VALUES ('2026-09-08 10:00:00', 'm', 4016, 16384)")
            _run_030(conn)

            by_id = {r["request_id"]: dict(r) for r in conn.execute(
                "SELECT request_id, input_tokens, cached_tokens FROM request_logs")}
            assert by_id["exclusive"] == {
                "request_id": "exclusive", "input_tokens": 305 + 221952,
                "cached_tokens": 221952}
            assert by_id["inclusive"] == {
                "request_id": "inclusive", "input_tokens": 89179, "cached_tokens": 88960}

            stats = dict(conn.execute(
                "SELECT input_tokens, cached_tokens FROM request_stats_minute"
            ).fetchone())
            assert stats == {"input_tokens": 4016 + 16384, "cached_tokens": 16384}

    def test_creation_tokens_are_folded_too(self, db):
        db.initialize_tables()
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO request_logs "
                "(request_id, model, input_tokens, cached_tokens, prompt_partial_cached) "
                "VALUES ('c', 'm', 10, 0, 400)")
            _run_030(conn)
            row = dict(conn.execute(
                "SELECT input_tokens FROM request_logs WHERE request_id = 'c'"
            ).fetchone())
            assert row["input_tokens"] == 410

    def test_idempotent(self, db):
        db.initialize_tables()
        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO request_logs "
                "(request_id, model, input_tokens, cached_tokens) "
                "VALUES ('exclusive', 'm', 305, 221952)")
            _run_030(conn)
            first = dict(conn.execute(
                "SELECT input_tokens FROM request_logs WHERE request_id = 'exclusive'"
            ).fetchone())
            _run_030(conn)  # 第二次不应再累加
            second = dict(conn.execute(
                "SELECT input_tokens FROM request_logs WHERE request_id = 'exclusive'"
            ).fetchone())
            assert first == second == {"input_tokens": 305 + 221952}


class TestMigration030SchemaTolerance:
    """Intermediate-version databases may lack a table the other statement needs."""

    def test_missing_stats_table(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            _logs_table(conn)
            conn.execute(
                "INSERT INTO request_logs "
                "(request_id, model, input_tokens, cached_tokens) VALUES ('a', 'm', 10, 500)")
            _run_030(conn)
            assert dict(conn.execute(
                "SELECT input_tokens FROM request_logs WHERE request_id = 'a'"
            ).fetchone()) == {"input_tokens": 510}
        finally:
            conn.close()

    def test_missing_logs_table(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            _stats_table(conn)
            conn.execute(
                "INSERT INTO request_stats_minute "
                "(bucket, model, input_tokens, cached_tokens) "
                "VALUES ('b', 'm', 10, 500)")
            _run_030(conn)
            assert dict(conn.execute(
                "SELECT input_tokens FROM request_stats_minute WHERE bucket = 'b'"
            ).fetchone()) == {"input_tokens": 510}
        finally:
            conn.close()

    def test_logs_without_creation_column(self):
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        try:
            _logs_table(conn, with_creation=False)
            conn.execute(
                "INSERT INTO request_logs "
                "(request_id, model, input_tokens, cached_tokens) VALUES ('a', 'm', 10, 500)")
            _run_030(conn)
            assert dict(conn.execute(
                "SELECT input_tokens FROM request_logs WHERE request_id = 'a'"
            ).fetchone()) == {"input_tokens": 510}
        finally:
            conn.close()
