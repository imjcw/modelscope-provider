"""Repository for provider_types table CRUD.

供应商类型：type_key（唯一标识，accounts.provider_type 引用它）、name、
strategy_type（限流策略种类：header_based / fixed_window）、config（策略参数 JSON）。
"""
import json
import logging
from typing import List, Optional

from core.database import DatabaseManager

logger = logging.getLogger(__name__)


class ProviderTypeRepository:
    """Repository for provider_types table CRUD."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    @staticmethod
    def _normalize(row) -> dict:
        d = dict(row)
        # config 以 JSON 文本存储，读出时解析为 dict 方便前端使用
        try:
            d["config"] = json.loads(d.get("config") or "{}")
        except (ValueError, TypeError):
            d["config"] = {}
        d["built_in"] = bool(d.get("built_in"))
        return d

    def find_all(self) -> List[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM provider_types ORDER BY built_in DESC, id ASC"
            )
            return [self._normalize(r) for r in cursor.fetchall()]

    def find_by_id(self, type_id: int) -> Optional[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM provider_types WHERE id = ?", (type_id,)
            )
            row = cursor.fetchone()
            return self._normalize(row) if row else None

    def find_by_type_key(self, type_key: str) -> Optional[dict]:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM provider_types WHERE type_key = ?", (type_key,)
            )
            row = cursor.fetchone()
            return self._normalize(row) if row else None

    def create(self, type_key: str, name: str, description: str = "",
               strategy_type: str = "header_based", config: dict = None,
               color: str = "#89b4fa", built_in: bool = False) -> dict:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO provider_types
                   (type_key, name, description, strategy_type, config, color, built_in)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (type_key, name, description, strategy_type,
                 json.dumps(config or {}), color, 1 if built_in else 0),
            )
            conn.commit()
            new_id = cursor.lastrowid
            logger.info(f"Created provider type {type_key} (id={new_id})")
            return self.find_by_id(new_id)

    def update(self, type_id: int, **kwargs) -> Optional[dict]:
        allowed = {"type_key", "name", "description", "strategy_type", "config", "color"}
        fields = {}
        for k, v in kwargs.items():
            if k not in allowed:
                continue
            fields[k] = json.dumps(v) if k == "config" else v
        if not fields:
            return None
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [type_id]
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE provider_types SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values,
            )
        return self.find_by_id(type_id)

    def delete(self, type_id: int) -> bool:
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM provider_types WHERE id = ?", (type_id,)
            )
            return cursor.rowcount > 0

    def count_accounts_by_type(self, type_key: str) -> int:
        """统计使用该类型的供应商数量（用于删除前校验）。"""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM accounts WHERE provider_type = ?", (type_key,)
            )
            return cursor.fetchone()[0]
