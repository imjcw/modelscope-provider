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

    def get_or_create_daily_quota(self, account_id: str, quota_limit: int, key_id: int = 0) -> QuotaInfo:
        """Get or create quota info for today, scoped to ``(account_id, key_id)``.

        Each API key of a supplier holds its own upstream daily quota, so the row
        is keyed per key (``key_id``); ``key_id = 0`` denotes the primary key.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to get existing quota for today
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens, unavailable_models
                FROM account_quotas
                WHERE account_id = ? AND key_id = ? AND quota_date = ?
            """, (account_id, key_id, today))

            row = cursor.fetchone()

            if row:
                # Update quota limit from API response
                cursor.execute("""
                    UPDATE account_quotas
                    SET quota_limit = ?
                    WHERE account_id = ? AND key_id = ? AND quota_date = ?
                """, (quota_limit, account_id, key_id, today))

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
                    (account_id, quota_date, key_id, quota_remaining, quota_limit, unavailable_models)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (account_id, today, key_id, 0, quota_limit, json.dumps([])))

                return QuotaInfo(
                    account_id=account_id,
                    quota_date=today,
                    quota_remaining=0,
                    quota_limit=quota_limit,
                    unavailable_models=set()
                )

    def update_quota(self, account_id: str, quota_remaining: int, quota_limit: int, key_id: int = 0):
        """Update quota for today, scoped to ``(account_id, key_id)``.

        Creates the entry if none exists. See :meth:`get_or_create_daily_quota`
        for the per-key rationale.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE account_quotas
                SET quota_remaining = ?, quota_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND key_id = ? AND quota_date = ?
            """, (quota_remaining, quota_limit, account_id, key_id, today))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, key_id, quota_remaining, quota_limit, unavailable_models)
                    VALUES (?, ?, ?, ?, ?, '[]')
                """, (account_id, today, key_id, quota_remaining, quota_limit))

    def mark_model_unavailable(self, account_id: str, model_name: str, key_id: int = 0):
        """Mark a model as unavailable for today, scoped to ``(account_id, key_id)``.

        A key whose supplier quota is exhausted for a model should only block THAT
        key — not every key of the supplier — so the row is keyed per key.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get current unavailable models
            cursor.execute("""
                SELECT unavailable_models FROM account_quotas
                WHERE account_id = ? AND key_id = ? AND quota_date = ?
            """, (account_id, key_id, today))

            row = cursor.fetchone()

            if row:
                current_models = _parse_models(row["unavailable_models"])
                current_models.add(model_name)
                cursor.execute("""
                    UPDATE account_quotas
                    SET unavailable_models = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND key_id = ? AND quota_date = ?
                """, (json.dumps(list(current_models)), account_id, key_id, today))
            else:
                # Create entry if not exists
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, key_id, quota_remaining, quota_limit, unavailable_models)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (account_id, today, key_id, 0, 0, json.dumps([model_name])))

    def get_account_info(self, account_id: str, key_id: Optional[int] = None) -> Optional[dict]:
        """Get account quota information.

        ``key_id`` — when given, return the single key's row; when ``None``
        (default), aggregate across all of the supplier's keys (per-key quotas
        summed) so the supplier-level dashboard reflects total capacity.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if key_id is not None:
                cursor.execute("""
                    SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens, unavailable_models, quota_date
                    FROM account_quotas
                    WHERE account_id = ? AND key_id = ? AND quota_date = ?
                """, (account_id, key_id, today))
                row = cursor.fetchone()
                if row:
                    return {
                        "account_id": account_id,
                        "key_id": key_id,
                        "quota_remaining": row["quota_remaining"] or 0,
                        "quota_limit": row["quota_limit"] or 0,
                        "total_input_tokens": row["total_input_tokens"] or 0,
                        "total_output_tokens": row["total_output_tokens"] or 0,
                        "unavailable_models": _parse_models(row["unavailable_models"]),
                        "quota_date": row["quota_date"],
                    }
                return None

            # Aggregate across all keys of this supplier
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens, unavailable_models, quota_date
                FROM account_quotas
                WHERE account_id = ? AND quota_date = ?
            """, (account_id, today))
            rows = cursor.fetchall()
            if not rows:
                return None
            rem = sum(r["quota_remaining"] or 0 for r in rows)
            lim = sum(r["quota_limit"] or 0 for r in rows)
            tin = sum(r["total_input_tokens"] or 0 for r in rows)
            tout = sum(r["total_output_tokens"] or 0 for r in rows)
            um: set = set()
            for r in rows:
                um |= _parse_models(r["unavailable_models"])
            return {
                "account_id": account_id,
                "quota_remaining": rem,
                "quota_limit": lim,
                "total_input_tokens": tin,
                "total_output_tokens": tout,
                "unavailable_models": um,
                "quota_date": rows[0]["quota_date"],
            }

    def get_unavailable_models_batch(self, account_ids) -> dict:
        """Batch fetch today's unavailable models for multiple accounts/keys.

        Returns ``{(account_id(str), key_id(int)): set(model_names)}``. Accounts
        or keys with no quota row for today are simply absent. Used by the router
        to skip candidates whose model quota is exhausted for the *specific key*,
        without an N+1 query per candidate.
        """
        if not account_ids:
            return {}
        today = self.db.get_today_date()
        ids = list(account_ids)
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            cursor = conn.execute(
                f"SELECT account_id, key_id, unavailable_models FROM account_quotas "
                f"WHERE account_id IN ({placeholders}) AND quota_date = ?",
                (*ids, today),
            )
            result = {}
            for row in cursor.fetchall():
                um = row["unavailable_models"]
                result[(row["account_id"], row["key_id"])] = _parse_models(um)
        return result

    def get_unavailable_models_by_account(self, account_ids) -> dict:
        """Per-supplier union of unavailable models across all keys.

        Returns ``{account_id(str): set(model_names)}``. Used by the legacy
        LoadBalancer path (which models a supplier as a single account, not per
        key). The per-key map from :meth:`get_unavailable_models_batch` is folded
        into one supplier-level set here.
        """
        per_key = self.get_unavailable_models_batch(account_ids)
        result: dict = {}
        for (account_id, _key_id), models in per_key.items():
            result.setdefault(account_id, set()).update(models)
        return result

    def reset_unavailable_models(self, account_id: str, key_id: Optional[int] = None):
        """Reset unavailable models (called when quota is reset).

        ``key_id`` — when given, reset only that key's row; when ``None`` (default)
        reset every key of the supplier for today.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if key_id is None:
                cursor.execute("""
                    UPDATE account_quotas
                    SET unavailable_models = '[]', updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND quota_date = ?
                """, (account_id, today))
            else:
                cursor.execute("""
                    UPDATE account_quotas
                    SET unavailable_models = '[]', updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND key_id = ? AND quota_date = ?
                """, (account_id, key_id, today))

    def record_usage(self, account_id: str, input_tokens: int, output_tokens: int, model_name: str, key_id: int = 0):
        """Record token usage for an account/key today, scoped to ``(account_id, key_id)``."""
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Try to get existing quota entry
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens
                FROM account_quotas
                WHERE account_id = ? AND key_id = ? AND quota_date = ?
            """, (account_id, key_id, today))

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
                    WHERE account_id = ? AND key_id = ? AND quota_date = ?
                """, (new_input, new_output, account_id, key_id, today))
            else:
                # Create new entry with usage tracked
                cursor.execute("""
                    INSERT INTO account_quotas
                    (account_id, quota_date, key_id, quota_remaining, quota_limit,
                     total_input_tokens, total_output_tokens, unavailable_models)
                    VALUES (?, ?, ?, 0, 0, ?, ?, '[]')
                """, (account_id, today, key_id, input_tokens, output_tokens))

    # ── Model-level quota methods ──

    def update_model_quota(self, account_id: str, model_name: str,
                           quota_remaining: int, quota_limit: int,
                           key_id: int = 0):
        """Update model-level quota for today. Creates entry if none exists.

        Args:
            account_id: supplier account id.
            model_name: catalog model name.
            quota_remaining: remaining quota from upstream headers.
            quota_limit: quota limit from upstream headers.
            key_id: supplier API key id (0 = primary key). Defaults to 0.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE model_quotas
                SET quota_remaining = ?, quota_limit = ?, updated_at = CURRENT_TIMESTAMP
                WHERE account_id = ? AND model_name = ? AND key_id = ? AND quota_date = ?
            """, (quota_remaining, quota_limit, account_id, model_name, key_id, today))

            if cursor.rowcount == 0:
                cursor.execute("""
                    INSERT INTO model_quotas
                    (account_id, model_name, key_id, quota_date, quota_remaining, quota_limit)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (account_id, model_name, key_id, today, quota_remaining, quota_limit))

    def record_model_usage(self, account_id: str, model_name: str,
                           input_tokens: int, output_tokens: int,
                           key_id: int = 0):
        """Record token usage for a model today. Creates entry if none exists.

        Args:
            account_id: supplier account id.
            model_name: catalog model name.
            input_tokens: input tokens to add.
            output_tokens: output tokens to add.
            key_id: supplier API key id (0 = primary key). Defaults to 0.
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT quota_remaining, quota_limit, total_input_tokens, total_output_tokens
                FROM model_quotas
                WHERE account_id = ? AND model_name = ? AND key_id = ? AND quota_date = ?
            """, (account_id, model_name, key_id, today))

            row = cursor.fetchone()

            if row:
                prev_input = row["total_input_tokens"] or 0
                prev_output = row["total_output_tokens"] or 0
                cursor.execute("""
                    UPDATE model_quotas
                    SET total_input_tokens = ?, total_output_tokens = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE account_id = ? AND model_name = ? AND key_id = ? AND quota_date = ?
                """, (prev_input + input_tokens, prev_output + output_tokens,
                      account_id, model_name, key_id, today))
            else:
                cursor.execute("""
                    INSERT INTO model_quotas
                    (account_id, model_name, key_id, quota_date, quota_remaining,
                     quota_limit, total_input_tokens, total_output_tokens)
                    VALUES (?, ?, ?, ?, 0, 0, ?, ?)
                """, (account_id, model_name, key_id, today, input_tokens, output_tokens))

    def get_model_quotas(self, account_id: str, key_id: int | None = None) -> list:
        """Get all model-level quotas for an account today.

        Args:
            account_id: supplier account id.
            key_id: when set, scope to this specific key. When None, return
                    all keys (aggregated across keys).
        """
        today = self.db.get_today_date()

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            if key_id is not None:
                cursor.execute("""
                    SELECT model_name, quota_remaining, quota_limit,
                           total_input_tokens, total_output_tokens
                    FROM model_quotas
                    WHERE account_id = ? AND key_id = ? AND quota_date = ?
                """, (account_id, key_id, today))
            else:
                cursor.execute("""
                    SELECT model_name, quota_remaining, quota_limit,
                           total_input_tokens, total_output_tokens
                    FROM model_quotas
                    WHERE account_id = ? AND quota_date = ?
                """, (account_id, today))
            return [dict(row) for row in cursor.fetchall()]

    def get_account_info_batch(self, account_ids, key_id: int | None = None) -> dict:
        """Batch version of :meth:`get_account_info`.

        Returns ``{account_id(str): info_dict}``. Accounts without a quota row
        for today are simply absent. Eliminates the N+1 query that
        ``get_model_quotas`` would otherwise issue once per supplier (P1).

        Args:
            account_ids: list of supplier account ids.
            key_id: when set, scope to this specific key (row in
                    ``account_quotas`` keyed by ``(account_id, key_id, quota_date)``).
        """
        if not account_ids:
            return {}
        today = self.db.get_today_date()
        ids = list(account_ids)
        result: dict = {}
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            if key_id is not None:
                cursor = conn.execute(
                    f"""SELECT account_id, quota_remaining, quota_limit,
                               total_input_tokens, total_output_tokens,
                               unavailable_models, quota_date
                        FROM account_quotas
                        WHERE account_id IN ({placeholders}) AND key_id = ? AND quota_date = ?""",
                    (*ids, key_id, today),
                )
            else:
                cursor = conn.execute(
                    f"""SELECT account_id, quota_remaining, quota_limit,
                               total_input_tokens, total_output_tokens,
                               unavailable_models, quota_date
                        FROM account_quotas
                        WHERE account_id IN ({placeholders}) AND quota_date = ?""",
                    (*ids, today),
                )
            for row in cursor.fetchall():
                acc = result.setdefault(row["account_id"], {
                    "account_id": row["account_id"],
                    "quota_remaining": 0,
                    "quota_limit": 0,
                    "total_input_tokens": 0,
                    "total_output_tokens": 0,
                    "unavailable_models": set(),
                    "quota_date": row["quota_date"],
                })
                acc["quota_remaining"] += row["quota_remaining"] or 0
                acc["quota_limit"] += row["quota_limit"] or 0
                acc["total_input_tokens"] += row["total_input_tokens"] or 0
                acc["total_output_tokens"] += row["total_output_tokens"] or 0
                acc["unavailable_models"] |= _parse_models(row["unavailable_models"])
        return result

    def get_model_quotas_batch(self, account_ids, key_id: int | None = None) -> dict:
        """Batch version of :meth:`get_model_quotas`.

        Returns ``{account_id(str): [model_quota_rows]}``. Used by
        ``get_model_quotas`` to load every supplier's model quotas in a single
        query instead of one per supplier (P1).

        Args:
            account_ids: list of supplier account ids.
            key_id: when set, scope to this specific key. When None, return
                    all keys (aggregated across keys).
        """
        if not account_ids:
            return {}
        today = self.db.get_today_date()
        ids = list(account_ids)
        result: dict = {aid: [] for aid in ids}
        with self.db.get_connection() as conn:
            placeholders = ",".join("?" * len(ids))
            if key_id is not None:
                rows = conn.execute(
                    f"""SELECT account_id, model_name, quota_remaining, quota_limit,
                               total_input_tokens, total_output_tokens
                        FROM model_quotas
                        WHERE account_id IN ({placeholders}) AND key_id = ? AND quota_date = ?""",
                    (*ids, key_id, today),
                ).fetchall()
            else:
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
