"""Lightweight schema migration framework."""

import core.migrations.migrations  # noqa: F401  # triggers @register for all versioned migrations
from core.migrations.base import Migration
from core.migrations.migrator import Migrator
from core.migrations.registry import get_all_migrations, register

__all__ = ["Migration", "Migrator", "get_all_migrations", "register"]
