"""Tests for AdminService.cleanup_old_logs triggering VACUUM.

Regression: logs were deleted on schedule but the SQLite file size never
changed, because DELETE alone does not reclaim disk space.
"""
from unittest.mock import Mock

from provider.services.admin_service import AdminService


def _make_service(deleted: int, db=None, log_repo_db=None):
    config_repo = Mock()
    config_repo.get.return_value = "1"
    log_repo = Mock()
    log_repo.delete_older_than.return_value = deleted
    log_repo.db = log_repo_db
    return AdminService(
        account_repo=Mock(),
        mapping_repo=Mock(),
        config_repo=config_repo,
        log_repo=log_repo,
        db=db,
    )


def test_cleanup_calls_vacuum_when_rows_deleted():
    db = Mock()
    svc = _make_service(deleted=42, db=db)
    svc.cleanup_old_logs()
    db.vacuum.assert_called_once()


def test_cleanup_skips_vacuum_when_nothing_deleted():
    db = Mock()
    svc = _make_service(deleted=0, db=db)
    svc.cleanup_old_logs()
    db.vacuum.assert_not_called()


def test_cleanup_falls_back_to_log_repo_db():
    repo_db = Mock()
    svc = _make_service(deleted=3, db=None, log_repo_db=repo_db)
    svc.cleanup_old_logs()
    repo_db.vacuum.assert_called_once()


def test_vacuum_failure_does_not_break_cleanup():
    db = Mock()
    db.vacuum.side_effect = RuntimeError("db locked")
    svc = _make_service(deleted=7, db=db)
    # Must not raise
    svc.cleanup_old_logs()
    db.vacuum.assert_called_once()
