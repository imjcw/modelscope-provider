import os
import pytest
from pathlib import Path
from provider.core.database import DatabaseManager
from provider.core.migrations import Migrator


BASE_DIR = Path(__file__).resolve().parent


@pytest.fixture(autouse=True)
def _clean_db_file(tmp_path, request):
    """每个测试自动清理/重建独立测试数据库。

    核心逻辑：
    1. 每个测试使用 tmp_path 下的独立 DB 文件，避免跨测试 UNIQUE 冲突。
    2. autouse=True 确保所有测试（含不显式使用 database fixture 的）都获得隔离环境。
    3. tmp_path 由 pytest 在 fixture teardown 时自动删除，无需手动清理。
    """
    db_path = tmp_path / "test.db"
    test_url = f"sqlite:///{db_path}"
    os.environ["DATABASE_URL"] = test_url

    # 初始化表 + 运行迁移（幂等，每次从零开始）
    db = DatabaseManager(test_url)
    db.initialize_tables()
    Migrator(db).run()
    db.close()

    yield test_url

    # tmp_path 由 pytest 自动清理，无需手动操作


@pytest.fixture
def database(_clean_db_file):
    """Database manager fixture — 每个测试独立 SQLite 文件。"""
    url = _clean_db_file
    db = DatabaseManager(url)
    yield db
    db.close()


@pytest.fixture
def db_connection(database):
    """Database connection fixture via context manager."""
    with database.get_connection() as conn:
        yield conn
