import json
from typing import Optional
from dataclasses import dataclass
from models.account import ModelScopeAccount


def _parse_models(text) -> set:
    """Safely parse a JSON array of model names.

    Returns an empty set for ``None``/empty/invalid-JSON input instead of
    raising — a corrupted ``unavailable_models`` cell should degrade to
    "nothing marked unavailable", not crash the routing/quota path.
    """
    if not text:
        return set()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return set()
    if not isinstance(data, list):
        return set()
    return set(data)


@dataclass
class QuotaInfo:
    """Quota information for an account."""
    account_id: str
    quota_date: str
    quota_remaining: int
    quota_limit: int
    unavailable_models: set


class QuotaRepository:
    """Repository for quota state storage."""

    def __init__(self, database):
        self.db = database

    def get_or_create_daily_quota(self, account_id: str, quota_limit: int) -> QuotaInfo:
        """Get or create quota info for today."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to get existing quota for today
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens, unavailable_models
                FROM account_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))

            row = cursor.fetchone()

            if row:
                # Update quota limit from API response
                cursor.execute("""
                    UPDATE account_quotas
                    SET quota_limit = ?
                    WHERE account_id = ? AND quota_date = ?
                """, (quota_limit, account_id, today))

                return QuotaInfo(
                    account_id=account_id,
                    quota_date=today,
                    quota_remaining=row["quota_remaining"] or 0,
                    quota_limit=quota_limit,
                    unavailable_models=_parse_models(row["unavailable_models"])
                )
            else:
                # Create new quota entry
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, quota_remaining, quota_limit, unavailable_models)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, today, 0, quota_limit, json.dumps([])))

                return QuotaInfo(
                    account_id=account_id,
                    quota_date=today,
                    quota_remaining=0,
                    quota_limit=quota_limit,
                    unavailable_models=set()
                )

    def update_quota(self, account_id: str, quota_remaining: int, quota_limit: int):
        """Update quota for today. Creates entry if none exists."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE account_quotas
                SET quota_remaining = ?, quota_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND quota_date = ?
            """, (quota_remaining, quota_limit, account_id, today))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, quota_remaining, quota_limit, unavailable_models)
                    VALUES (?, ?, ?, ?, '[]')
                """, (account_id, today, quota_remaining, quota_limit))

    def mark_model_unavailable(self, account_id: str, model_name: str):
        """Mark a model as unavailable for today."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get current unavailable models
            cursor.execute("""
                SELECT unavailable_models FROM account_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))

            row = cursor.fetchone()

            if row:
                current_models = _parse_models(row["unavailable_models"])
                current_models.add(model_name)
                cursor.execute("""
                    UPDATE account_quotas
                    SET unavailable_models = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND quota_date = ?
                """, (json.dumps(list(current_models)), account_id, today))
            else:
                # Create entry if not exists
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, quota_remaining, quota_limit, unavailable_models)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, today, 0, 0, json.dumps([model_name])))

    def get_account_info(self, account_id: str) -> Optional[dict]:
        """Get account quota information."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens, unavailable_models, quota_date
                FROM account_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))

            row = cursor.fetchone()
            if row:
                return {
                    "account_id": account_id,
                    "quota_remaining": row["quota_remaining"] or 0,
                    "quota_limit": row["quota_limit"] or 0,
                    "total_input_tokens": row["total_input_tokens"] or 0,
                    "total_output_tokens": row["total_output_tokens"] or 0,
                    "unavailable_models": _parse_models(row["unavailable_models"]),
                    "quota_date": row["quota_date"]
                }
            return None

    def get_unavailable_models_batch(self, account_ids) -> dict:
        """Batch fetch today's unavailable models for multiple accounts.

        Returns ``{account_id(str): set(model_names)}``. Accounts with no quota
        row for today map to an empty set. Used by the router to skip candidates
        whose model quota is exhausted, without an N+1 query per candidate.
        """
        if not account_ids:
            return {}
        today = self.db.get_today_date()
        ids = list(account_ids)
        result = {aid: set() for aid in ids}
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"SELECT account_id, unavailable_models FROM account_quotas "
                f"WHERE account_id IN ({placeholders}) AND quota_date = ?",
                (*ids, today),
            )
            for row in cursor.fetchall():
                um = row["unavailable_models"]
                result[row["account_id"]] = _parse_models(um)
        return result

    def reset_unavailable_models(self, account_id: str):
        """Reset unavailable models (called when quota is reset)."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE account_quotas
                SET unavailable_models = '[]', updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))

    def record_usage(self, account_id: str, input_tokens: int, output_tokens: int, model_name: str):
        """Record token usage for an account today. Creates entry if none exists."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to get existing quota entry
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens
                FROM account_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))

            row = cursor.fetchone()

            if row:
                # Accumulate usage in existing entry
                prev_input = row["total_input_tokens"] or 0
                prev_output = row["total_output_tokens"] or 0
                new_input = prev_input + input_tokens
                new_output = prev_output + output_tokens
                cursor.execute("""
                    UPDATE account_quotas
                    SET total_input_tokens = ?, total_output_tokens = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND quota_date = ?
                """, (new_input, new_output, account_id, today))
            else:
                # Create new entry with usage tracked
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, quota_remaining, quota_limit,
                     total_input_tokens, total_output_tokens, unavailable_models)
                    VALUES (?, ?, 0, 0, ?, ?, '[]')
                """, (account_id, today, input_tokens, output_tokens))

    # ── Model-level quota methods ──

    def update_model_quota(self, account_id: str, model_name: str,
                           quota_remaining: int, quota_limit: int):
        """Update model-level quota for today. Creates entry if none exists."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE model_quotas
                SET quota_remaining = ?, quota_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND model_name = ? AND quota_date = ?
            """, (quota_remaining, quota_limit, account_id, model_name, today))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO model_quotas
                    (account_id, model_name, quota_date, quota_remaining, quota_limit)
                    VALUES (?, ?, ?, ?, ?)
                """, (account_id, model_name, today, quota_remaining, quota_limit))

    def record_model_usage(self, account_id: str, model_name: str,
                           input_tokens: int, output_tokens: int):
        """Record token usage for a model today. Creates entry if none exists."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens
                FROM model_quotas
                WHERE account_id = ? AND model_name = ? AND quota_date = ?
            """, (account_id, model_name, today))

            row = cursor.fetchone()

            if row:
                prev_input = row["total_input_tokens"] or 0
                prev_output = row["total_output_tokens"] or 0
                cursor.execute("""
                    UPDATE model_quotas
                    SET total_input_tokens = ?, total_output_tokens = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND model_name = ? AND quota_date = ?
                """, (prev_input + input_tokens, prev_output + output_tokens,
                      account_id, model_name, today))
            else:
                cursor.execute("""
                    INSERT INTO model_quotas
                    (account_id, model_name, quota_date, quota_remaining,
                     quota_limit, total_input_tokens, total_output_tokens)
                    VALUES (?, ?, ?, 0, 0, ?, ?)
                """, (account_id, model_name, today, input_tokens, output_tokens))

    def get_model_quotas(self, account_id: str) -> list:
        """Get all model-level quotas for an account today."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT model_name, quota_remaining, quota_limit,
                       total_input_tokens, total_output_tokens
                FROM model_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))
            return [dict(row) for row in cursor.fetchall()]

    def get_account_info_batch(self, account_ids) -> dict:
        """Batch version of :meth:`get_account_info`.

        Returns ``{account_id(str): info_dict}``. Accounts without a quota row
        for today are simply absent. Eliminates the N+1 query that
        ``get_model_quotas`` would otherwise issue once per supplier (P1).
        """
        if not account_ids:
            return {}
        today = self.db.get_today_date()
        ids = list(account_ids)
        result: dict = {}
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"""SELECT account_id, quota_remaining, quota_limit,
                           total_input_tokens, total_output_tokens,
                           unavailable_models, quota_date
                    FROM account_quotas
                    WHERE account_id IN ({placeholders}) AND quota_date = ?""",
                (*ids, today),
            )
            for row in cursor.fetchall():
                result[row["account_id"]] = {
                    "account_id": row["account_id"],
                    "quota_remaining": row["quota_remaining"] or 0,
                    "quota_limit": row["quota_limit"] or 0,
                    "total_input_tokens": row["total_input_tokens"] or 0,
                    "total_output_tokens": row["total_output_tokens"] or 0,
                    "unavailable_models": _parse_models(row["unavailable_models"]),
                    "quota_date": row["quota_date"],
                }
        return result

    def get_model_quotas_batch(self, account_ids) -> dict:
        """Batch version of :meth:`get_model_quotas`.

        Returns ``{account_id(str): [model_quota_rows]}``. Used by
        ``get_model_quotas`` to load every supplier's model quotas in a single
        query instead of one per supplier (P1).
        """
        if not account_ids:
            return {}
        today = self.db.get_today_date()
        ids = list(account_ids)
        result: dict = {aid: [] for aid in ids}
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            rows = conn.execute(
                f"""SELECT account_id, model_name, quota_remaining, quota_limit,
                           total_input_tokens, total_output_tokens
                    FROM model_quotas
                    WHERE account_id IN ({placeholders}) AND quota_date = ?""",
                (*ids, today),
            ).fetchall()
            for row in rows:
                result.setdefault(row["account_id"], []).append(dict(row))
        return result
