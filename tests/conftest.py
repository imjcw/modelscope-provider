import pytest
import sqlite3
from pathlib import Path
from provider.core.database import DatabaseManager

BASE_DIR = Path(__file__).resolve().parent


@pytest.fixture
def test_db_url():
    """Test database URL."""
    return str(BASE_DIR / "modelscope_proxy_test.db")


@pytest.fixture
def database(test_db_url):
    """Database manager fixture."""
    db = DatabaseManager(test_db_url)
    db.initialize_tables()
    yield db
    # Cleanup
    db_path = Path(test_db_url)
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def db_connection(database):
    """Database connection fixture via context manager."""
    with database.get_connection() as conn:
        yield conn
