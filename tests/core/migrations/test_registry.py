import pytest
from core.migrations.base import Migration
from core.migrations.registry import clear_registry, get_all_migrations, register


@pytest.fixture(autouse=True)
def _clean_registry():
    """Snapshot and restore the global registry around each test.

    The migration modules register themselves at import time (once per
    session). Clearing the global list after a test would leave it empty for
    the rest of the session, which breaks every other test module that relies
    on ``Migrator.run()`` applying the real migrations. So we clear before the
    test for isolation, then restore the real registry afterwards.
    """
    from core.migrations.registry import _ALL_MIGRATIONS

    saved = list(_ALL_MIGRATIONS)
    clear_registry()
    yield
    _ALL_MIGRATIONS[:] = saved


def test_register_and_get_all_migrations():

    @register
    class FakeMigration(Migration):
        version = 1
        description = "fake"

        def up(self, conn):
            pass

    migrations = get_all_migrations()
    assert len(migrations) == 1
    assert migrations[0].version == 1
    assert migrations[0].description == "fake"


def test_get_all_migrations_sorted_by_version():

    @register
    class M2(Migration):
        version = 2
        description = "second"

        def up(self, conn):
            pass

    @register
    class M1(Migration):
        version = 1
        description = "first"

        def up(self, conn):
            pass

    migrations = get_all_migrations()
    assert [m.version for m in migrations] == [1, 2]


def test_migration_base_is_abc():
    with pytest.raises(TypeError):
        Migration()  # abstract class
