import pytest
import sqlite3

from provider.repositories.account_repository import AccountRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository


@pytest.fixture
def supplier_model_repo(database):
    return SupplierModelRepository(database)


@pytest.fixture
def sample_supplier(database, supplier_model_repo):
    """Create a test supplier and return its dict."""
    acc_repo = AccountRepository(database)
    return acc_repo.create(
        name="test-supplier",
        api_key="ms-test-key",
        base_url="https://api.modelscope.test/v1",
    )


def test_create_and_find_by_supplier(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    result = supplier_model_repo.create(
        supplier_id=sid, model_name="qwen-max", model_type="text", context_length=32768
    )
    assert result["supplier_id"] == sid
    assert result["model_name"] == "qwen-max"
    assert result["model_type"] == "text"
    assert result["context_length"] == 32768

    models = supplier_model_repo.find_by_supplier(sid)
    assert len(models) == 1
    assert models[0]["model_name"] == "qwen-max"


def test_create_duplicate_raises_uniqueness_error(
    database, supplier_model_repo, sample_supplier
):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")
    with pytest.raises(sqlite3.IntegrityError):
        supplier_model_repo.create(sid, "qwen-max", "text")


def test_delete_by_id(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    row = supplier_model_repo.create(sid, "glm-4", "text", context_length=128000)
    mid = row["id"]
    assert supplier_model_repo.delete(mid) is True
    assert supplier_model_repo.delete(mid) is False  # already deleted
    assert supplier_model_repo.find_by_supplier(sid) == []


def test_delete_by_supplier(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")
    supplier_model_repo.create(sid, "glm-4", "code")
    assert supplier_model_repo.delete_by_supplier(sid) == 2
    assert supplier_model_repo.find_by_supplier(sid) == []


def test_bulk_upsert_replaces_all(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    # First upsert
    supplier_model_repo.bulk_upsert(
        sid,
        [
            {"model_name": "qwen-max", "model_type": "text", "context_length": 32768},
            {"model_name": "glm-4", "model_type": "text", "context_length": 128000},
        ],
    )
    models = supplier_model_repo.find_by_supplier(sid)
    assert len(models) == 2

    # Second upsert — replaces all
    supplier_model_repo.bulk_upsert(
        sid,
        [
            {"model_name": "qwen-vl", "model_type": "image", "context_length": None},
        ],
    )
    models = supplier_model_repo.find_by_supplier(sid)
    assert len(models) == 1
    assert models[0]["model_name"] == "qwen-vl"
    assert models[0]["model_type"] == "image"
    assert models[0]["context_length"] is None


def test_find_suppliers_for_model_only_active(
    database, supplier_model_repo, sample_supplier
):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")

    result = supplier_model_repo.find_suppliers_for_model("qwen-max")
    assert len(result) == 1
    assert result[0]["id"] == sid

    # Disable supplier
    acc_repo = AccountRepository(database)
    acc_repo.update(sid, status="disabled")

    result = supplier_model_repo.find_suppliers_for_model("qwen-max")
    assert result == []


def test_find_suppliers_for_model_no_match(
    database, supplier_model_repo, sample_supplier
):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")

    result = supplier_model_repo.find_suppliers_for_model("nonexistent")
    assert result == []


def test_cascade_on_supplier_delete(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")
    acc_repo = AccountRepository(database)
    acc_repo.delete(sid)
    assert supplier_model_repo.find_by_supplier(sid) == []
