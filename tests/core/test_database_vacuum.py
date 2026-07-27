"""Tests for DatabaseManager.vacuum().

Regression: SQLite DELETE only marks pages as free — the .db file never
shrinks. After bulk log deletion, vacuum() must reclaim the disk space.
"""
import os

from provider.repositories.log_repository import LogRepository


def _db_file_size(database) -> int:
    """Total on-disk size (main db + WAL) after a full checkpoint."""
    return os.path.getsize(database.db_url)


def test_vacuum_shrinks_db_file_after_bulk_delete(database):
    log_repo = LogRepository(database)

    # Insert many rows with a fat payload so the db file grows noticeably.
    payload = "x" * 5000
    for i in range(200):
        log_repo.create(
            request_id=f"req-{i}",
            model="test-model",
            raw_request=payload,
            raw_response=payload,
        )

    size_after_insert = _db_file_size(database)

    # Delete everything (cutoff far in the future).
    deleted = log_repo.delete_older_than("2999-01-01 00:00:00")
    assert deleted == 200

    database.vacuum()
    size_after_vacuum = _db_file_size(database)

    # The file must actually shrink after VACUUM.
    assert size_after_vacuum < size_after_insert, (
        f"expected file to shrink: before={size_after_insert}, "
        f"after vacuum={size_after_vacuum}"
    )


def test_vacuum_is_safe_on_empty_database(database):
    # Should not raise even when there is nothing to reclaim.
    database.vacuum()
    database.vacuum()
