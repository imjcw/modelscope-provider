"""Core configuration and database utilities."""

from provider.core.database import DatabaseManager

try:
    from provider.core.config import ConfigManager
except ModuleNotFoundError:
    ConfigManager = None  # config.py not yet available in this phase

__all__ = ["ConfigManager", "DatabaseManager"]
