"""Test cases for AliasRouter."""
import pytest
from provider.services.alias_router import AliasRouter, RoutingResult
from models.account import ModelScopeAccount


class MockMappingModelRepo:
    def __init__(self, entries):
        # entries: dict[alias, list[dict]]
        self._entries = entries

    def find_by_alias(self, alias):
        return self._entries.get(alias, [])


class MockAccountRepo:
    def __init__(self, accounts):
        # accounts: dict[id, dict]
        self._accounts = accounts

    def find_by_id(self, account_id):
        return self._accounts.get(account_id)


class MockConfigRepo:
    def __init__(self, strategy="round_robin"):
        self._strategy = strategy

    def get(self, key):
        if key == "load_balancer_strategy":
            return self._strategy
        return None


def _make_account(id, name="Supplier", api_key="key", base_url="https://api.test.com"):
    return {
        "id": id,
        "account_id": f"acc-{id}",
        "name": name,
        "api_key": api_key,
        "base_url": base_url,
        "status": "active",
    }


class TestAliasRouterRoute:
    """route() 方法的核心行为。"""

    def test_returns_none_when_no_bindings(self):
        """无绑定时返回 None。"""
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({}),
            account_repo=MockAccountRepo({}),
            config_repo=MockConfigRepo(),
        )
        result = router.route("unknown-alias")
        assert result is None

    def test_returns_none_when_bindings_but_no_valid_accounts(self):
        """有绑定但账号不存在时返回 None。"""
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [{"id": 1, "supplier_id": 999, "model_name": "qwen"}]
            }),
            account_repo=MockAccountRepo({}),  # 无账号
            config_repo=MockConfigRepo(),
        )
        result = router.route("my-alias")
        assert result is None

    def test_round_robin_selects_candidates(self):
        """round_robin 策略在候选间轮转。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("round_robin"),
        )
        r1 = router.route("my-alias")
        assert r1.account.account_id == "acc-1"
        assert r1.model_name == "qwen"
        r2 = router.route("my-alias")
        assert r2.account.account_id == "acc-2"
        assert r2.model_name == "gpt-4o"
        r3 = router.route("my-alias")
        assert r3.account.account_id == "acc-1"  # wraps

    def test_random_strategy_selects_from_candidates(self):
        """random 策略从候选中随机选。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("random"),
        )
        results = [router.route("my-alias") for _ in range(20)]
        model_names = {r.model_name for r in results}
        assert model_names == {"qwen", "gpt-4o"}

    def test_least_conn_strategy(self):
        """least_conn 策略选择连接数最少的候选。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("least_conn"),
        )
        # 第一次选第一个（都是 0 连接）
        r1 = router.route("my-alias")
        assert r1 is not None
        # 第二次选另一个
        r2 = router.route("my-alias")
        assert r2 is not None
        assert r1.model_name != r2.model_name

    def test_invalid_strategy_falls_back_to_round_robin(self):
        """无效策略名时 fallback 到 round_robin。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("invalid_strategy"),
        )
        r1 = router.route("my-alias")
        assert r1.model_name == "qwen"
        r2 = router.route("my-alias")
        assert r2.model_name == "gpt-4o"

    def test_result_is_routing_result_dataclass(self):
        """返回值是 RoutingResult 类型。"""
        accounts = {1: _make_account(1)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [{"id": 1, "supplier_id": 1, "model_name": "qwen"}]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo(),
        )
        result = router.route("my-alias")
        assert isinstance(result, RoutingResult)
        assert isinstance(result.account, ModelScopeAccount)
