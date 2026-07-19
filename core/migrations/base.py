"""Migration abstract base class."""

from abc import ABC, abstractmethod
import sqlite3


class Migration(ABC):
    """Abstract base for all schema migrations.

    Subclasses define ``version`` (unique, increasing int),
    ``description`` (human-readable), and implement ``up()``.
    ``down()`` is optional — raise NotImplementedError if unsupported.
    """

    version: int
    description: str

    @abstractmethod
    def up(self, conn: sqlite3.Connection) -> None:
        """Apply the migration. Must be idempotent."""
        ...

    def down(self, conn: sqlite3.Connection) -> None:
        """Revert the migration. Override in subclass if rollback is supported."""
        raise NotImplementedError(
            f"Migration {self.version} ({self.description}) does not support down()"
        )
