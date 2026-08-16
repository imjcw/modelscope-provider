"""Tests for AdminService.get_model_quotas (per-model window strategy surfacing).

These lock in the behavior added so that the "按模型窗口" policy is reflected
on the model: each model row carries its window strategy type, effective
window/max-requests, live remaining/limit, and whether it has a per-model
override configured on the provider type.
"""
import pytest

from provider.repositories.account_repository import AccountRepository
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.log_repository import LogRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.repositories.quota_repository import QuotaRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository
from provider.repositories.provider_type_repository import ProviderTypeRepository
from provider.services.admin_service import AdminService
from provider.services.providers.per_model import PerModelFixedWindowStrategy

# Defaults from services/providers/per_model.py: 5h / 1500
_DEFAULT_WINDOW_SECONDS = 5 * 3600
_DEFAULT_MAX_REQUESTS = 1500


@pytest.fixture
def svc(database):
    account_repo = AccountRepository(database)
    mapping_repo = MappingRepository(database)
    config_repo = ConfigRepository(database)
    log_repo = LogRepository(database)
    quota_repo = QuotaRepository(database)
    supplier_model_repo = SupplierModelRepository(database)
    provider_type_repo = ProviderTypeRepository(database)

    # Provider type that uses the per-model window strategy, with an explicit
    # override for model "m1".
    provider_type_repo.create(
        type_key="pt-per-model",
        name="Per-model PT",
        strategy_type="fixed_window_per_model",
        config={"models": {"m1": {"window_seconds": 600, "max_requests": 5}}},
    )

    acc = account_repo.create(
        name="Supplier A",
        api_keys=["k"],
        base_url="http://x",
        provider_type="pt-per-model",
    )
    sid = acc["id"]
    aid = acc["account_id"]

    supplier_model_repo.create(sid, "m1", "text", 8000)
    supplier_model_repo.create(sid, "m2", "text", 8000)

    # header-driven (modelscope-style) quota rows, independent of the window
    quota_repo.update_model_quota(aid, "m1", quota_remaining=80, quota_limit=100)
    quota_repo.update_model_quota(aid, "m2", quota_remaining=40, quota_limit=100)

    strategy = PerModelFixedWindowStrategy(
        database, model_configs={"m1": {"window_seconds": 600, "max_requests": 5}}
    )
    rate_limit_strategies = {"pt-per-model": strategy}

    return AdminService(
        account_repo,
        mapping_repo,
        config_repo,
        log_repo,
        quota_repo=quota_repo,
        supplier_model_repo=supplier_model_repo,
        provider_type_repo=provider_type_repo,
        rate_limit_strategies=rate_limit_strategies,
    )


def test_per_model_window_surfaced_on_models(svc):
    rows = svc.get_model_quotas()
    by_model = {r["model_name"]: r for r in rows}
    assert set(by_model) == {"m1", "m2"}

    # Model with a per-model override -> custom window reflected.
    m1 = by_model["m1"]
    assert m1["strategy_type"] == "fixed_window_per_model"
    assert m1["window_seconds"] == 600
    assert m1["max_requests"] == 5
    assert m1["window_quota_limit"] == 5
    assert m1["window_quota_remaining"] == 5
    assert m1["has_custom_window"] is True
    # header-driven quota is still surfaced alongside the window info.
    assert m1["quota_remaining"] == 80 and m1["quota_limit"] == 100

    # Model without an override -> falls back to the strategy defaults.
    m2 = by_model["m2"]
    assert m2["strategy_type"] == "fixed_window_per_model"
    assert m2["window_seconds"] == _DEFAULT_WINDOW_SECONDS
    assert m2["max_requests"] == _DEFAULT_MAX_REQUESTS
    assert m2["has_custom_window"] is False


def test_no_strategy_instance_yields_none_window_fields(svc, database):
    # A second account whose provider_type has no strategy instance registered.
    account_repo = AccountRepository(database)
    supplier_model_repo = SupplierModelRepository(database)
    acc = account_repo.create(
        name="Supplier B",
        api_keys=["k2"],
        base_url="http://y",
        provider_type="modelscope",
    )
    supplier_model_repo.create(acc["id"], "m3", "text", 8000)

    m3 = next(r for r in svc.get_model_quotas() if r["model_name"] == "m3")
    # "modelscope" is a built-in provider type backed by the header-based
    # strategy, which has no fixed window -> window fields are None.
    assert m3["strategy_type"] == "header_based"
    assert m3["window_seconds"] is None
    assert m3["window_quota_remaining"] is None
    assert m3["has_custom_window"] is False


def test_multi_key_scales_window_limit(svc, database):
    """Extra active keys multiply the window quota (N keys → N× limit)."""
    account_repo = AccountRepository(database)
    supplier_model_repo = SupplierModelRepository(database)
    acc = account_repo.create(
        name="Supplier MultiKey",
        api_keys=["k1"],
        base_url="http://x",
        provider_type="pt-per-model",
    )
    sid = acc["id"]
    # m1 is overridden to max_requests=5 on the provider type config.
    supplier_model_repo.create(sid, "m1", "text", 8000)

    def _m1_for(sup_name):
        return next(
            r for r in svc.get_model_quotas()
            if r["model_name"] == "m1" and r["supplier_name"] == sup_name
        )

    # No extra keys → base limit unchanged (5, from the m1 override).
    row = _m1_for("Supplier MultiKey")
    assert row["max_requests"] == 5
    assert row["window_quota_limit"] == 5

    # Add two more active keys → 3 keys total → limit 3×5 = 15.
    account_repo.add_api_key(sid, "k2")
    account_repo.add_api_key(sid, "k3")

    row = _m1_for("Supplier MultiKey")
    assert row["max_requests"] == 15
    assert row["window_quota_limit"] == 15
    assert row["window_quota_remaining"] == 15


def test_frozen_keys_not_counted(svc, database):
    """Frozen keys must not contribute to the multiplier."""
    account_repo = AccountRepository(database)
    supplier_model_repo = SupplierModelRepository(database)
    acc = account_repo.create(
        name="Supplier Frozen",
        api_keys=["k1"],
        base_url="http://x",
        provider_type="pt-per-model",
    )
    sid = acc["id"]
    supplier_model_repo.create(sid, "m2", "text", 8000)

    key = account_repo.add_api_key(sid, "k2")
    account_repo.update_api_key_status(key["id"], "frozen")

    row = next(
        r for r in svc.get_model_quotas()
        if r["model_name"] == "m2" and r["supplier_name"] == "Supplier Frozen"
    )
    # m2 uses the default limit (1500); the frozen key is not counted → 1×1500.
    assert row["max_requests"] == _DEFAULT_MAX_REQUESTS
    assert row["window_quota_limit"] == _DEFAULT_MAX_REQUESTS


def test_single_key_keeps_base_limit(svc):
    """Regression: a single-key account keeps the base window limit."""
    m1 = next(
        r for r in svc.get_model_quotas()
        if r["model_name"] == "m1" and r["supplier_name"] == "Supplier A"
    )
    assert m1["max_requests"] == 5
    assert m1["window_quota_limit"] == 5


def test_model_usage_scoped_to_key(svc):
    import uuid
    from datetime import datetime, timezone as _tz

    acc = svc.account_repo.find_by_name("Supplier A")
    aid = acc["account_id"]
    sid = acc["id"]
    now = datetime.now(_tz.utc).strftime("%Y-%m-%d %H:%M:%S.") + "000"

    # 前端传的是 account_api_keys.id，需要拿真实 id
    keys = svc.account_repo.find_all_api_keys(sid)
    assert len(keys) >= 1
    pk_key_id = keys[0]["id"]

    # 添加第二个 key
    svc.account_repo.add_api_key(sid, "k2")
    keys2 = svc.account_repo.find_all_api_keys(sid)
    assert len(keys2) == 2
    sk_key_id = keys2[1]["id"]

    # request_logs 写入逻辑 key_id（0=主, 1=第二）
    svc.log_repo.create(
        str(uuid.uuid4()), "m1", "m1", aid, "Supplier A", 200,
        input_tokens=10, output_tokens=20, api_key_id=0, timestamp=now,
    )
    svc.log_repo.create(
        str(uuid.uuid4()), "m1", "m1", aid, "Supplier A", 200,
        input_tokens=100, output_tokens=200, api_key_id=1, timestamp=now,
    )

    svc.quota_repo.update_model_quota(aid, "m1", 50, 200, key_id=1)

    # 传入 account_api_keys.id（模拟前端行为）
    rows_k0 = {r["model_name"]: r for r in svc.get_model_quotas(days=0, key_id=pk_key_id)}
    rows_k1 = {r["model_name"]: r for r in svc.get_model_quotas(days=0, key_id=sk_key_id)}

    # token 用量按 key 区分
    assert rows_k0["m1"]["today_input_tokens"] == 10
    assert rows_k0["m1"]["today_output_tokens"] == 20
    assert rows_k1["m1"]["today_input_tokens"] == 100
    assert rows_k1["m1"]["today_output_tokens"] == 200
    assert rows_k0["m1"]["today_input_tokens"] != rows_k1["m1"]["today_input_tokens"]

    # 额度也按 key 区分
    assert rows_k0["m1"]["quota_remaining"] == 80
    assert rows_k0["m1"]["quota_limit"] == 100
    assert rows_k1["m1"]["quota_remaining"] == 50
    assert rows_k1["m1"]["quota_limit"] == 200
    assert rows_k0["m1"]["quota_remaining"] != rows_k1["m1"]["quota_remaining"]
    assert rows_k0["m1"]["quota_remaining"] != rows_k1["m1"]["quota_remaining"]
