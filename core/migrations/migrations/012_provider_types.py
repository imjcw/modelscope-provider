"""Migration 012: create provider_types table and seed built-in types.

供应商类型管理：每种类型绑定一种限流策略（strategy_type）及其可配置参数（config）。
创建供应商时选择某个类型，即套用对应策略。
"""

import json
import sqlite3
from core.migrations.base import Migration
from core.migrations.registry import register

_BUILTINS = [
    # type_key, name, description, strategy_type, config, color
    (
        "modelscope", "ModelScope",
        "被动式限流：依赖上游响应头（modelscope-ratelimit-*）回写配额。",
        "header_based", {}, "#89b4fa",
    ),
    (
        "sensetime", "商汤",
        "主动式固定窗口计数器：窗口内请求数达到上限即拦截。",
        "fixed_window", {"window_seconds": 18000, "max_requests": 1500}, "#f38ba8",
    ),
]


@register
class ProviderTypes(Migration):
    version = 12
    description = "Create provider_types table and seed built-in provider types"

    def up(self, conn: sqlite3.Connection) -> None:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type_key TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                strategy_type TEXT NOT NULL DEFAULT 'header_based',
                config TEXT NOT NULL DEFAULT '{}',
                color TEXT NOT NULL DEFAULT '#89b4fa',
                built_in INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for type_key, name, desc, strategy_type, config, color in _BUILTINS:
            conn.execute(
                """INSERT OR IGNORE INTO provider_types
                   (type_key, name, description, strategy_type, config, color, built_in)
                   VALUES (?, ?, ?, ?, ?, ?, 1)""",
                (type_key, name, desc, strategy_type, json.dumps(config), color),
            )
