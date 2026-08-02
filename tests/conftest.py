import os
import pytest
import sqlite3
from pathlib import Path
from provider.core.database import DatabaseManager
from provider.core.migrations import Migrator

BASE_DIR = Path(__file__).resolve().parent

# ── 确保 pytest 测试不影响 .env 指向的数据库 ──
# 在导入任何会读 .env 的模块之前，覆盖 DATABASE_URL
_test_db_path = str(BASE_DIR / "modelscope_proxy_test.db")
_original_db_url = os.environ.get("DATABASE_URL")
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"


@pytest.fixture(autouse=True)
def set_test_db_url():
    """确保每个测试都使用测试数据库，并在测试后恢复 original。

    仅靠模块级别的 os.environ 设置是不够的：cleanup 测试之后
    的下一个测试会拿到被恢复的 original URL（或删除后的状态），
    从而错误地指向生产数据库。这个 fixture 在每个测试开始前
    重新设置测试 DB URL。
    """
    os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
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
    Migrator(db).run()
    yield db
    # Close pooled connections first — on Windows the DB file cannot be
    # deleted while any connection is open (PermissionError: WinError 32).
    db.close()
    db_path = Path(_test_db_path)
    if db_path.exists():
        db_path.unlink()


@pytest.fixture
def db_connection(database):
    """Database connection fixture via context manager."""
    with database.get_connection() as conn:
        yield conn
