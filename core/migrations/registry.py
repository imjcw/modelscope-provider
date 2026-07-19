"""Migration registry — collects all registered migration classes."""

from core.migrations.base import Migration

_ALL_MIGRATIONS: list[type[Migration]] = []


def register(cls: type[Migration]) -> type[Migration]:
    """Class decorator: register a migration class in the global registry."""
    if cls not in _ALL_MIGRATIONS:
        _ALL_MIGRATIONS.append(cls)
    return cls


def get_all_migrations() -> list[Migration]:
    """Instantiate and return all registered migrations sorted by version."""
    return sorted([cls() for cls in _ALL_MIGRATIONS], key=lambda m: m.version)


def clear_registry() -> None:
    """Reset registry (for testing only)."""
    _ALL_MIGRATIONS.clear()
