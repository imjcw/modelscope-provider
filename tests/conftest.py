import os
import pytest
import sqlite3
from pathlib import Path
from provider.core.database import DatabaseManager

BASE_DIR = Path(__file__).resolve().parent

# ── 确保 pytest 测试不影响 .env 指向的数据库 ──
# 在导入任何会读 .env 的模块之前，覆盖 DATABASE_URL
_test_db_path = str(BASE_DIR / "modelscope_proxy_test.db")
_original_db_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"


@pytest.fixture(autouse=True)
def cleanup_test_db_url():
    """Restore original DATABASE_URL after each test."""
    yield
    if _original_db_url is not None:
        os.environ["DATABASE_URL"] = _original_db_url
    elif "DATABASE_URL" in os.environ:
        del os.environ["DATABASE_URL"]


@pytest.fixture
def test_db_url():
    """Test database URL (isolated from .env)."""
    return f"sqlite:///{_test_db_path}"


@pytest.fixture
def database(test_db_url):
    """Database manager fixture — uses isolated test DB, cleaned up after."""
    db = DatabaseManager(test_db_url)
    db.initialize_tables()
    yield db
    db_path = Path(_test_db_path)
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def db_connection(database):
    """Database connection fixture via context manager."""
    with database.get_connection() as conn:
        yield conn
