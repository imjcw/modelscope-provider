"""Test cases for MappingModelRepository."""
import pytest
from provider.core.database import DatabaseManager
from provider.repositories.mapping_model_repository import MappingModelRepository


@pytest.fixture
def test_db():
    """Create test database with accounts."""
    db = DatabaseManager('modelscope_proxy_test.db')
    db.initialize_tables()
    # Create test accounts for foreign key constraint
    from provider.repositories.account_repository import AccountRepository
    acc_repo = AccountRepository(db)
    acc1 = acc_repo.create('Supplier1', 'key1', 'https://api1.test.com')
    acc2 = acc_repo.create('Supplier2', 'key2', 'https://api2.test.com')
    # Verify accounts exist
    assert acc1 is not None
    assert acc2 is not None
    assert acc1['id'] == 1
    assert acc2['id'] == 2
    yield db, acc1, acc2
    # Cleanup
    import sqlite3
    conn = sqlite3.connect('modelscope_proxy_test.db')
    conn.execute("DROP TABLE IF EXISTS mapping_models")
    conn.execute("DROP TABLE IF EXISTS model_mappings")
    conn.execute("DROP TABLE IF EXISTS accounts")
    conn.commit()
    conn.close()


@pytest.fixture
def repo(test_db):
    db, acc1, acc2 = test_db
    return MappingModelRepository(db)


def test_find_by_alias_empty(repo):
    """Test finding by alias when none exists."""
    result = repo.find_by_alias('nonexistent')
    assert result == []


def test_add_model(repo, test_db):
    """Test adding a model to a mapping alias."""
    db, acc1, acc2 = test_db
    print(f"Adding model with supplier_id={acc1['id']}")
    result = repo.add_model('test-alias', acc1['id'], 'qwen-max')
    assert result['alias_name'] == 'test-alias'
    assert result['supplier_id'] == acc1['id']
    assert result['model_name'] == 'qwen-max'
    assert 'id' in result
    assert 'created_at' in result


def test_add_model_duplicate(repo, test_db):
    """Test that adding duplicate model raises error."""
    db, acc1, acc2 = test_db
    repo.add_model('test-alias', acc1['id'], 'qwen-max')
    # SQLite will raise UNIQUE constraint error
    with pytest.raises(Exception):
        repo.add_model('test-alias', acc1['id'], 'qwen-max')


def test_find_by_alias(repo, test_db):
    """Test finding multiple models for an alias."""
    db, acc1, acc2 = test_db
    repo.add_model('test-alias', acc1['id'], 'qwen-max')
    repo.add_model('test-alias', acc2['id'], 'deepseek-chat')
    results = repo.find_by_alias('test-alias')
    assert len(results) == 2
    model_names = {r['model_name'] for r in results}
    assert model_names == {'qwen-max', 'deepseek-chat'}
    # Verify ordering by id
    assert results[0]['model_name'] == 'qwen-max'
    assert results[1]['model_name'] == 'deepseek-chat'


def test_remove_model(repo, test_db):
    """Test removing a model from an alias."""
    db, acc1, acc2 = test_db
    added = repo.add_model('test-alias', acc1['id'], 'qwen-max')
    model_id = added['id']
    result = repo.remove_model(model_id)
    assert result is True
    assert len(repo.find_by_alias('test-alias')) == 0


def test_remove_model_not_found(repo):
    """Test removing a non-existent model."""
    result = repo.remove_model(99999)
    assert result is False


def test_get_by_supplier(repo, test_db):
    """Test getting all models for a specific supplier."""
    db, acc1, acc2 = test_db
    repo.add_model('alias1', acc1['id'], 'qwen-max')
    repo.add_model('alias2', acc1['id'], 'deepseek-chat')
    repo.add_model('alias3', acc2['id'], 'ernie-bot')
    results = repo.get_by_supplier(acc1['id'])
    assert len(results) == 2
    assert results[0]['alias_name'] in ['alias1', 'alias2']
    assert results[1]['alias_name'] in ['alias1', 'alias2']


def test_multiple_aliases_same_model(repo, test_db):
    """Test that same model can exist under different aliases."""
    db, acc1, acc2 = test_db
    repo.add_model('alias1', acc1['id'], 'qwen-max')
    repo.add_model('alias2', acc2['id'], 'qwen-max')
    results1 = repo.find_by_alias('alias1')
    results2 = repo.find_by_alias('alias2')
    assert len(results1) == 1
    assert len(results2) == 1
    assert results1[0]['model_name'] == 'qwen-max'
    assert results2[0]['model_name'] == 'qwen-max'


def test_updated_at_timestamp(repo, test_db):
    """Test that updated_at is set when adding a model."""
    db, acc1, acc2 = test_db
    import time
    time.sleep(0.1)  # Ensure timestamp difference
    result1 = repo.add_model('test-alias', acc1['id'], 'qwen-max')
    time.sleep(0.1)
    result2 = repo.add_model('test-alias', acc2['id'], 'deepseek-chat')
    # updated_at should be different for each
    assert result1['updated_at'] != result2['updated_at']
