import json
from typing import Optional
from dataclasses import dataclass
from models.account import ModelScopeAccount


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
                    unavailable_models=set(json.loads(row["unavailable_models"]) if row["unavailable_models"] else [])
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
                current_models = set(json.loads(row["unavailable_models"]) if row["unavailable_models"] else [])
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
                    "unavailable_models": set(json.loads(row["unavailable_models"]) if row["unavailable_models"] else []),
                    "quota_date": row["quota_date"]
                }
            return None

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
