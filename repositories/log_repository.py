import json
import logging
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class LogRepository:
    """Repository for request_logs table."""

    def __init__(self, db: DatabaseManager):
        self.db = db

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
               response_headers: str = None) -> int:
        """Insert a log entry."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO request_logs
                   (request_id, model, actual_model_id, account_id, account_name, status_code,
                    input_tokens, output_tokens, latency_ms, is_stream,
                    error_message, raw_request, raw_response,
                    request_start, first_response, end_time,
                    cached_tokens, prompt_partial_cached,
                    client_key_name, response_headers)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (request_id, model, actual_model_id, account_id, account_name, status_code,
                 input_tokens, output_tokens, latency_ms, is_stream,
                 error_message, raw_request, raw_response,
                 request_start, first_response, end_time,
                 cached_tokens, prompt_partial_cached,
                 client_key_name, response_headers),
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
        """Count requests today."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM request_logs WHERE date(timestamp) = date('now')"
            )
            return cursor.fetchone()[0]
