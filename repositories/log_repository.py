import json
import logging
from datetime import datetime
from typing import List, Optional

from core.database import DatabaseManager
from core.timezone import TZ

logger = logging.getLogger(__name__)


class LogRepository:
    """Repository for request_logs table."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    @staticmethod
    def _floor_minute(ts: str) -> str:
        """Floor a timestamp string to minute precision (bucket alignment).

        ``bucket`` in request_stats_minute is always ``YYYY-MM-DD HH:MM:00``.
        Flooring start/end ensures ``bucket >= start`` comparisons include the
        correct minute bucket even when callers pass sub-minute timestamps.
        """
        return ts[:16] + ":00" if len(ts) >= 16 else ts

    @staticmethod
    def _normalize_bucket(ts: str) -> str:
        """Normalise an arbitrary timestamp into the stats bucket key.

        Rows in ``request_stats_minute`` are keyed by minute buckets formatted
        as ``YYYY-MM-DD HH:MM:00`` in the project timezone (Asia/Shanghai).
        Incoming timestamps may be space- or ``T``-separated, naive or
        timezone-aware (UTC ``Z`` / ``+00:00`` or ``+08:00``). Always convert
        to Shanghai-local time, floor to the minute and use a space separator
        so the bucket matches what the query side (``get_window_stats``) builds.
        """
        raw = (ts or "").strip()
        dt = None
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            try:
                dt = datetime.strptime(raw[:19], "%Y-%m-%d %H:%M:%S")
            except ValueError:
                dt = None
        if dt is None:
            dt = datetime.now(TZ)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        dt = dt.astimezone(TZ).replace(second=0, microsecond=0)
        return dt.strftime("%Y-%m-%d %H:%M:%S")

    def create(self, request_id: str, model: str, actual_model_id: str = None,
               account_id: str = None, account_name: str = None,
               status_code: int = None,
               input_tokens: int = 0, output_tokens: int = 0,
               latency_ms: int = None, is_stream: bool = False,
               error_message: str = None, raw_request: str = None,
               raw_response: str = None,
               request_start: str = None, first_response: str = None, end_time: str = None,
               cached_tokens: int = 0, prompt_partial_cached: int = 0,
               client_key_name: str = None,
               response_headers: str = None,
               api_key_id: int = 0) -> int:
        """Insert a log entry."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO request_logs
                   (request_id, model, actual_model_id, account_id, account_name, status_code,
                    input_tokens, output_tokens, latency_ms, is_stream,
                    error_message, raw_request, raw_response,
                    request_start, first_response, end_time,
                    cached_tokens, prompt_partial_cached,
                    client_key_name, response_headers, api_key_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (request_id, model, actual_model_id, account_id, account_name, status_code,
                 input_tokens, output_tokens, latency_ms, is_stream,
                 error_message, raw_request, raw_response,
                 request_start, first_response, end_time,
                 cached_tokens, prompt_partial_cached,
                 client_key_name, response_headers, api_key_id),
            )
            return cursor.lastrowid

    def find_by_request_id(self, request_id: str) -> Optional[dict]:
        """Get a single log entry by request ID."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM request_logs WHERE request_id = ?", (request_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_by_id(self, log_id: int) -> Optional[dict]:
        """Get a single log entry by internal id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM request_logs WHERE id = ?", (log_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def find_all(self, page: int = 0, page_size: int = 50,
                 status_code: int = None, account_id: str = None,
                 model: str = None, is_stream: bool = None,
                 start_time: str = None, end_time: str = None,
                 client_key_name: str = None) -> tuple:
        """Paginated query with filters. Returns (records, total)."""
        where_parts = []
        params = []

        if status_code is not None:
            where_parts.append("status_code = ?")
            params.append(status_code)
        if account_id:
            where_parts.append("account_id = ?")
            params.append(account_id)
        if model:
            where_parts.append("model = ?")
            params.append(model)
        if is_stream is not None:
            where_parts.append("is_stream = ?")
            params.append(1 if is_stream else 0)
        if start_time:
            where_parts.append("timestamp >= ?")
            params.append(start_time)
        if end_time:
            where_parts.append("timestamp <= ?")
            params.append(end_time)
        if client_key_name:
            where_parts.append("client_key_name = ?")
            params.append(client_key_name)

        where_clause = " WHERE " + " AND ".join(where_parts) if where_parts else ""

        # Total count
        with self.db.get_connection() as conn:
            cursor = conn.execute(f"SELECT COUNT(*) FROM request_logs{where_clause}", params)
            total = cursor.fetchone()[0]

            # Paginated results
            offset = page * page_size
            query = f"""SELECT * FROM request_logs{where_clause}
                        ORDER BY timestamp DESC LIMIT ? OFFSET ?"""
            cursor = conn.execute(query, params + [page_size, offset])
            records = [dict(row) for row in cursor.fetchall()]

        return records, total

    def count_today(self) -> int:
        """Count requests today (Asia/Shanghai), consistent with dashboard stats."""
        from core.timezone import today

        today_str = today()
        with self.db.get_connection() as conn:
            # `timestamp` is stored as UTC (CURRENT_TIMESTAMP). Shift it to
            # Shanghai before extracting the date so "today" matches the
            # dashboard, which floors stats by Shanghai local time.
            cursor = conn.execute(
                "SELECT COUNT(*) FROM request_logs "
                "WHERE strftime('%Y-%m-%d', timestamp, '+8 hours') = ?",
                (today_str,),
            )
            return cursor.fetchone()[0]

    def delete_older_than(self, cutoff: str) -> int:
        """Delete log entries with timestamp older than the cutoff.

        Args:
            cutoff: ISO-formatted timestamp string ("YYYY-MM-DD HH:MM:SS").

        Returns:
            Number of deleted rows.
        """
        with self.db.get_connection() as conn:
            conn.execute(
                "DELETE FROM request_logs WHERE timestamp < ?",
                (cutoff,),
            )
            result = conn.execute("SELECT changes()").fetchone()
            return result[0] if result else 0

    # ── 分钟级统计聚合 ──────────────────────────────────────────────────

    def upsert_stats(
        self,
        timestamp: str,
        model: str,
        account_id: str,
        virtual_model: str = "",
        client_key_name: str = "",
        status_code: int = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        latency_ms: int = None,
        cached_tokens: int = 0,
    ) -> None:
        """Upsert a minute-level stats row for the given timestamp.

        Called once per request alongside ``create()`` to keep aggregated
        statistics independent from the raw log table.
        """
        # Normalise to Shanghai-local, minute-floored, space-separated bucket so
        # it matches the query side (get_window_stats).
        bucket = LogRepository._normalize_bucket(timestamp)
        success = 1 if status_code is not None and 0 < status_code < 400 else 0
        lat_val = latency_ms if latency_ms is not None else 0
        lat_count = 1 if latency_ms is not None else 0

        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO request_stats_minute
                   (bucket, model, virtual_model, account_id, client_key_name,
                    requests, success, input_tokens, output_tokens,
                    latency_sum, latency_count, cached_tokens)
                   VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(bucket, model, account_id, client_key_name)
                   DO UPDATE SET
                       requests = requests + 1,
                       success = success + excluded.success,
                       input_tokens = input_tokens + excluded.input_tokens,
                       output_tokens = output_tokens + excluded.output_tokens,
                       latency_sum = latency_sum + excluded.latency_sum,
                       latency_count = latency_count + excluded.latency_count,
                       cached_tokens = cached_tokens + excluded.cached_tokens,
                       virtual_model = excluded.virtual_model""",
                (bucket, model, virtual_model, account_id, client_key_name,
                 success, input_tokens, output_tokens,
                 lat_val, lat_count, cached_tokens),
            )

    def query_stats_summarize(self, start: str, end: str) -> dict:
        """Aggregated stats over a time range (replaces ``summarize_window``).

        Returns ``{total, success, total_tokens, input_tokens, output_tokens,
        cached_tokens, avg_latency_ms}``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(requests), 0) AS total,
                          COALESCE(SUM(success), 0) AS success,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(input_tokens + output_tokens), 0) AS total_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                          CASE WHEN SUM(latency_count) > 0
                               THEN CAST(SUM(latency_sum) AS REAL) / SUM(latency_count)
                               ELSE NULL END AS avg_latency_ms
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?""",
                (s, e),
            ).fetchone()
            return dict(row)

    def query_stats_aggregate(
        self, start: str, end: str, bucket_seconds: int,
    ) -> List[dict]:
        """Bucketed stats over a time range (replaces ``aggregate_window``).

        Returns ``[{bucket_start, total, success, total_tokens, input_tokens,
        output_tokens, cached_tokens, avg_latency_ms}]``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        # bucket 列存储的是上海本地时间字符串。日级（>=86400s）分桶若用 strftime('%s', bucket)
        # 会把上海时间当成 UTC，导致桶界与前端/Python 按上海时区对齐的网格错开 8 小时，
        # by_epoch 映射全部落空 —— 7 天 / 30 天窗口 series 全为 0，图表空白。
        # 因此日级桶直接按上海本地日历截断到当天 00:00，子级桶沿用原 epoch 整除（其粒度均整除
        # 8h，上海界与 UTC 界一致，无需调整）。
        if bucket_seconds >= 86400:
            bucket_expr = "strftime('%Y-%m-%d 00:00:00', bucket)"
            params = (s, e)
        else:
            bucket_expr = ("strftime('%Y-%m-%d %H:%M:%S',"
                           " (strftime('%s', bucket) / ?) * ?, 'unixepoch')")
            params = (bucket_seconds, bucket_seconds, s, e)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                f"SELECT {bucket_expr} AS bucket_start,"
                "              COALESCE(SUM(requests), 0) AS total,"
                "              COALESCE(SUM(success), 0) AS success,"
                "              COALESCE(SUM(input_tokens), 0) AS input_tokens,"
                "              COALESCE(SUM(output_tokens), 0) AS output_tokens,"
                "              COALESCE(SUM(cached_tokens), 0) AS cached_tokens,"
                "              COALESCE(SUM(input_tokens + output_tokens), 0) AS total_tokens,"
                "              CASE WHEN SUM(latency_count) > 0"
                "                   THEN CAST(SUM(latency_sum) AS REAL) / SUM(latency_count)"
                "                   ELSE NULL END AS avg_latency_ms"
                " FROM request_stats_minute"
                " WHERE bucket >= ? AND bucket <= ?"
                " GROUP BY bucket_start ORDER BY bucket_start",
                params,
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_per_model(self, start: str, end: str) -> List[dict]:
        """Per-model stats over a time range (replaces ``per_model_stats``).

        Grouped by ``(model, account_id)`` so that the same model name bound to
        different suppliers is reported separately, ordered by total desc.

        Returns ``[{model, account_id, total, success, input_tokens,
        output_tokens, cached_tokens}]``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT model,
                          account_id,
                          COALESCE(SUM(requests), 0) AS total,
                          COALESCE(SUM(success), 0) AS success,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?
                   GROUP BY model, account_id ORDER BY (SUM(input_tokens) + SUM(output_tokens)) DESC""",
                (s, e),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_status_breakdown(self, start: str, end: str) -> List[dict]:
        """Status code breakdown over a time range (replaces ``status_code_breakdown``).

        Returns ``[{status_code, count}]`` ordered by count desc.

        NOTE: This still reads from ``request_logs`` because the stats table
        doesn't track per-status-code counts. Only logs within the retention
        window are available.
        """
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT status_code, COUNT(*) AS count
                   FROM request_logs
                   WHERE timestamp >= ? AND timestamp <= ?
                   GROUP BY status_code ORDER BY count DESC""",
                (start, end),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_by_models(
        self, start: str, models: List[str],
    ) -> List[dict]:
        """Aggregated stats for one or more models over a time range.

        Returns ``[{model, requests, success, input_tokens, output_tokens,
                     cached_tokens}]`` ordered by requests desc.
        """
        if not models:
            return []
        placeholders = ",".join("?" for _ in models)
        s = self._floor_minute(start)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                f"""SELECT model,
                          COALESCE(SUM(requests), 0) AS requests,
                          COALESCE(SUM(success), 0) AS success,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND model IN ({placeholders})
                   GROUP BY model ORDER BY requests DESC""",
                (s, *models),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_by_virtual_model(
        self, start: str, virtual_model: str,
    ) -> List[dict]:
        """Aggregated stats for a virtual model over a time range.

        Grouped by actual model name AND account (supplier), so that different
        suppliers sharing the same model name are reported separately instead
        of being merged into one row.

        Returns ``[{model, account_id, requests, success, input_tokens,
                     output_tokens, cached_tokens}]`` ordered by requests desc.
        """
        s = self._floor_minute(start)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT model,
                          account_id,
                          COALESCE(SUM(requests), 0) AS requests,
                          COALESCE(SUM(success), 0) AS success,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND virtual_model = ?
                   GROUP BY model, account_id ORDER BY requests DESC""",
                (s, virtual_model),
            )
            return [dict(r) for r in rows.fetchall()]

    # ── 基于 request_stats_minute 的只读查询 ──────────────────────────
    # 这些方法从分钟级聚合表读取，不受 request_logs 留存期限影响。

    def query_stats_client_key(self, today_start: str, key: str) -> dict:
        """汇总一个客户端 key 今日的用量。

        Returns ``{requests, input_tokens, output_tokens, cached_tokens}``.
        """
        s = self._floor_minute(today_start)
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(requests), 0) AS requests,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND client_key_name = ?""",
                (s, key),
            ).fetchone()
            return dict(row)

    def query_stats_key_summary(
        self, start: str, key: str,
    ) -> dict:
        """单 key 多日总体聚合。

        Returns ``{total, success, input_tokens, output_tokens, cached_tokens,
                   latency_sum, latency_count}``.
        """
        s = self._floor_minute(start)
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(requests), 0) AS total,
                          COALESCE(SUM(success), 0) AS success,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                          COALESCE(SUM(latency_sum), 0) AS latency_sum,
                          COALESCE(SUM(latency_count), 0) AS latency_count
                   FROM request_stats_minute
                   WHERE bucket >= ? AND client_key_name = ?""",
                (s, key),
            ).fetchone()
            return dict(row)

    def query_stats_key_per_model(
        self, start: str, key: str,
    ) -> List[dict]:
        """单 key 分模型聚合。

        Returns ``[{model, requests, success, input_tokens, output_tokens,
                     cached_tokens}]`` ordered by requests desc.
        """
        s = self._floor_minute(start)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT model,
                          COALESCE(SUM(requests), 0) AS requests,
                          COALESCE(SUM(success), 0) AS success,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND client_key_name = ?
                   GROUP BY model ORDER BY requests DESC""",
                (s, key),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_global(self, start: str, end: str) -> dict:
        """全局 totals 聚合。

        Returns ``{total, input_tokens, output_tokens, cached_tokens}``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(requests), 0) AS total,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?""",
                (s, e),
            ).fetchone()
            return dict(row)

    def query_stats_heatmap(self, start: str, end: str) -> List[dict]:
        """热力图数据：按 (weekday, hour) 计数。

        weekday 为 Python 风格 0=Monday, 6=Sunday（与 get_stats 的
        dict 键 ``"weekday,hour"`` 保持一致）。

        Returns ``[{weekday, hour, count}]``.
        """
        # SQLite strftime('%w', ...) 返回 0=Sun..6=Sat。转换为 0=Mon..6=Sun：
        # ((%w + 6) % 7)
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT ((CAST(strftime('%w', bucket) AS INTEGER) + 6) % 7) AS weekday,
                          CAST(strftime('%H', bucket) AS INTEGER) AS hour,
                          SUM(requests) AS count
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?
                   GROUP BY weekday, hour
                   ORDER BY weekday, hour""",
                (s, e),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_daily_trend(self, start: str, end: str) -> List[dict]:
        """每日趋势。

        Returns ``[{date, input_tokens, output_tokens, cached_tokens}]``
        ordered by date asc. ``total = input + output`` computed in service.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT date(bucket) AS date,
                          COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?
                   GROUP BY date(bucket) ORDER BY date(bucket)""",
                (s, e),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_model_usage(self, start: str, end: str) -> List[dict]:
        """分模型 token 用量。

        Returns ``[{model, tokens}]`` ordered by tokens desc.
        ``tokens = input_tokens + output_tokens``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT model,
                          COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ? AND model IS NOT NULL
                   GROUP BY model ORDER BY tokens DESC""",
                (s, e),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_daily_model_usage(
        self, start: str, end: str,
    ) -> List[dict]:
        """每日每个模型的 token 用量。

        Returns ``[{date, model, tokens}]`` ordered by date asc, tokens desc.
        ``tokens = input_tokens + output_tokens``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT date(bucket) AS date,
                          model,
                          COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ? AND model IS NOT NULL
                   GROUP BY date(bucket), model
                   ORDER BY date(bucket), tokens DESC""",
                (s, e),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_supplier_daily(
        self, start: str, end: str,
    ) -> List[dict]:
        """供应商每日用量。

        Returns ``[{account_id, date, tokens}]`` ordered by account_id, date.
        ``tokens = input_tokens + output_tokens``.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT account_id,
                          date(bucket) AS date,
                          COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?
                   GROUP BY account_id, date(bucket)
                   ORDER BY account_id, date(bucket)""",
                (s, e),
            )
            return [dict(r) for r in rows.fetchall()]

    def query_stats_today_token_usage(
        self, account_id: str, model: str, start_of_day: str, end_of_day: str,
    ) -> tuple:
        """按 account_id + model 聚合今日的 input/output/cached tokens（stats 表）。

        Returns ``(input_tokens, output_tokens, cached_tokens)``. ``cached_tokens``
        is surfaced separately so callers like ``get_model_quotas`` can show the
        cache-hit column in the supplier model-usage panel.
        """
        s, e = self._floor_minute(start_of_day), self._floor_minute(end_of_day)
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?
                     AND account_id = ? AND model = ?""",
                (s, e, account_id, model),
            ).fetchone()
            return (row["input_tokens"], row["output_tokens"], row["cached_tokens"])

    def query_stats_model_aggregate(
        self, account_id: str, model: str, start: str, end: str,
    ) -> tuple:
        """Aggregate requests + tokens for one account+model over a time range.

        Returns (input_tokens, output_tokens, cached_tokens, requests, success)
        so callers (e.g. get_model_quotas with a days range) can compute
        the request success rate and per-range token usage in a single query.
        """
        s, e = self._floor_minute(start), self._floor_minute(end)
        with self.db.get_connection() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens,
                          COALESCE(SUM(output_tokens), 0) AS output_tokens,
                          COALESCE(SUM(cached_tokens), 0) AS cached_tokens,
                          COALESCE(SUM(requests), 0) AS requests,
                          COALESCE(SUM(success), 0) AS success
                   FROM request_stats_minute
                   WHERE bucket >= ? AND bucket <= ?
                     AND account_id = ? AND model = ?""",
                (s, e, account_id, model),
            ).fetchone()
            return (
                row["input_tokens"], row["output_tokens"], row["cached_tokens"],
                row["requests"], row["success"],
            )

    # ── (removed dead legacy methods) ──────────────────────────────────
    # aggregate_window, summarize_window, status_code_breakdown, and
    # per_model_stats have been removed. They were all replaced by the
    # request_stats_minute-based query_* methods above.
