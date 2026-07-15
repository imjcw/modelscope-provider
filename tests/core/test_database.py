import pytest
from provider.core.database import DatabaseManager


def test_database_initialization(database):
    """Test that database tables are created successfully."""
    assert database.get_today_date() is not None


def test_get_today_date(database):
    """Test date format."""
    date_str = database.get_today_date()
    assert len(date_str) == 10
    assert date_str.startswith("20")
