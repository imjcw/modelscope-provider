import json
from typing import Optional
from dataclasses import dataclass
from provider.models.account import ModelScopeAccount


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
                SELECT quota_remaining, quota_limit, unavailable_models
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
        """Update quota for today."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE account_quotas
                SET quota_remaining = ?, quota_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND quota_date = ?
            """, (quota_remaining, quota_limit, account_id, today))

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
                SELECT quota_remaining, quota_limit, unavailable_models, quota_date
                FROM account_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))

            row = cursor.fetchone()
            if row:
                return {
                    "account_id": account_id,
                    "quota_remaining": row["quota_remaining"] or 0,
                    "quota_limit": row["quota_limit"] or 0,
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
