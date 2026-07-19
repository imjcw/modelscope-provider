import pytest
from core.migrations.base import Migration
from core.migrations.registry import clear_registry, get_all_migrations, register


def test_register_and_get_all_migrations():
    clear_registry()

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
    clear_registry()

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
