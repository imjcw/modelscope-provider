"""Test cases for MappingModelRepository.

Uses the project-standard ``database`` fixture (conftest autouse sets up an
isolated, migrated tmp_path SQLite file) instead of a hardcoded DB path.
"""
import pytest
from provider.repositories.mapping_model_repository import MappingModelRepository
from provider.repositories.account_repository import AccountRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository
from provider.repositories.mapping_repository import MappingRepository


@pytest.fixture
def test_db(database):
    """Create test data: accounts, parent model_mappings and supplier_models.

    The ``database`` fixture already provides an isolated, migrated SQLite file
    (no hardcoded path, auto-cleaned by pytest's tmp_path teardown).
    """
    db = database
    acc_repo = AccountRepository(db)
    sm_repo = SupplierModelRepository(db)
    mapping_repo = MappingRepository(db)

    acc1 = acc_repo.create('Supplier1', 'https://api1.test.com', api_keys=['key1'])
    acc2 = acc_repo.create('Supplier2', 'https://api2.test.com', api_keys=['key2'])
    # Verify accounts exist
    assert acc1 is not None
    assert acc2 is not None
    assert acc1['id'] == 1
    assert acc2['id'] == 2

    # Create parent model_mappings entries (FK prerequisite for mapping_models)
    mapping_repo.create('test-alias', 'test-alias')
    mapping_repo.create('alias1', 'alias1')
    mapping_repo.create('alias2', 'alias2')
    mapping_repo.create('alias3', 'alias3')

    # Create supplier_models (FK prerequisite for mapping_models.supplier_model_id)
    sm_repo.create(acc1['id'], 'qwen-max', 'text')
    sm_repo.create(acc1['id'], 'qwen-plus', 'text')
    sm_repo.create(acc2['id'], 'deepseek-chat', 'text')
    sm_repo.create(acc2['id'], 'ernie-bot', 'text')

    # Helper to look up supplier_model id by (supplier_id, model_name)
    def _sm_id(sid, name):
        rows = sm_repo.find_by_supplier(sid)
        for r in rows:
            if r['model_name'] == name:
                return r['id']
        raise ValueError(f"supplier_model ({sid}, {name}) not found")

    yield db, acc1, acc2, sm_repo, _sm_id


@pytest.fixture
def repo(test_db):
    db, acc1, acc2, sm_repo, _sm_id = test_db
    return MappingModelRepository(db)


def test_find_by_alias_empty(repo):
    """Test finding by alias when none exists."""
    result = repo.find_by_alias('nonexistent')
    assert result == []


def test_add_model(repo, test_db):
    """Test adding a model to a mapping alias."""
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sid = _sm_id(acc1['id'], 'qwen-max')
    result = repo.add_model('test-alias', sid)
    assert result['alias_name'] == 'test-alias'
    assert result['supplier_model_id'] == sid
    assert result['supplier_id'] == acc1['id']
    assert result['model_name'] == 'qwen-max'
    assert 'id' in result
    assert 'created_at' in result


def test_add_model_duplicate(repo, test_db):
    """Test that adding duplicate model raises error."""
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sid = _sm_id(acc1['id'], 'qwen-max')
    repo.add_model('test-alias', sid)
    # SQLite will raise UNIQUE constraint error
    with pytest.raises(Exception):
        repo.add_model('test-alias', sid)


def test_find_by_alias(repo, test_db):
    """Test finding multiple models for an alias."""
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sm1 = _sm_id(acc1['id'], 'qwen-max')
    sm2 = _sm_id(acc2['id'], 'deepseek-chat')
    repo.add_model('test-alias', sm1)
    repo.add_model('test-alias', sm2)
    results = repo.find_by_alias('test-alias')
    assert len(results) == 2
    model_names = {r['model_name'] for r in results}
    assert model_names == {'qwen-max', 'deepseek-chat'}
    # Verify ordering by id
    assert results[0]['model_name'] == 'qwen-max'
    assert results[1]['model_name'] == 'deepseek-chat'


def test_remove_model(repo, test_db):
    """Test removing a model from an alias."""
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sid = _sm_id(acc1['id'], 'qwen-max')
    added = repo.add_model('test-alias', sid)
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
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sm1 = _sm_id(acc1['id'], 'qwen-max')
    sm2 = _sm_id(acc1['id'], 'qwen-plus')
    sm3 = _sm_id(acc2['id'], 'ernie-bot')
    repo.add_model('alias1', sm1)
    repo.add_model('alias2', sm2)
    repo.add_model('alias3', sm3)
    results = repo.get_by_supplier(acc1['id'])
    assert len(results) == 2
    assert results[0]['alias_name'] in ['alias1', 'alias2']
    assert results[1]['alias_name'] in ['alias1', 'alias2']


def test_multiple_aliases_same_model(repo, test_db):
    """Test that same model can exist under different aliases."""
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sm1 = _sm_id(acc1['id'], 'qwen-max')
    sm2 = _sm_id(acc2['id'], 'ernie-bot')
    repo.add_model('alias1', sm1)
    repo.add_model('alias2', sm2)
    results1 = repo.find_by_alias('alias1')
    results2 = repo.find_by_alias('alias2')
    assert len(results1) == 1
    assert len(results2) == 1
    assert results1[0]['model_name'] == 'qwen-max'
    assert results2[0]['model_name'] == 'ernie-bot'


def test_updated_at_timestamp(repo, test_db):
    """Test that updated_at is set when adding a model."""
    db, acc1, acc2, sm_repo, _sm_id = test_db
    sm1 = _sm_id(acc1['id'], 'qwen-max')
    sm2 = _sm_id(acc2['id'], 'deepseek-chat')
    import time
    result1 = repo.add_model('test-alias', sm1)
    time.sleep(1.1)  # SQLite CURRENT_TIMESTAMP has second-level precision
    result2 = repo.add_model('test-alias', sm2)
    # updated_at should be different for each
    assert result1['updated_at'] != result2['updated_at']
