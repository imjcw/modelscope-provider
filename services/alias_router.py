"""AliasRouter — 根据虚拟模型ID的绑定条目选择路由。"""
import logging
import random
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """路由结果：选中的账户 + 实际模型名。"""

    account: object       # ModelScopeAccount 实例
    model_name: str       # 直接发给下游的模型名


class AliasRouter:
    """根据虚拟模型ID的绑定条目选择路由。

    职责：
    1. 查找 alias 在 mapping_models 表中的所有绑定条目
    2. 有绑定时按策略选一个，返回 (account, model_name)
    3. 无绑定时返回 None（调用方 fallback 到旧逻辑）
    """

    def __init__(self, mapping_model_repo, account_repo, config_repo):
        self.mapping_model_repo = mapping_model_repo
        self.account_repo = account_repo
        self.config_repo = config_repo
        # round_robin 计数器按 alias 隔离
        self._rr_counters = {}
        # least_conn 策略的每条目请求计数
        self._conn_counts = {}

    def _get_strategy(self) -> str:
        """从 system_config 实时读取策略，默认 round_robin。"""
        val = self.config_repo.get("load_balancer_strategy")
        if val in ("round_robin", "least_conn", "random"):
            return val
        return "round_robin"

    def route(self, alias: str) -> Optional[RoutingResult]:
        """为 alias 选择一个绑定条目。

        Returns:
            RoutingResult（有绑定时）或 None（无绑定时）
        """
        entries = self.mapping_model_repo.find_by_alias(alias)
        if not entries:
            return None

        # 解析每个条目对应的 account
        candidates = []
        for entry in entries:
            account_dict = self.account_repo.find_by_id(entry["supplier_id"])
            if account_dict:
                candidates.append((account_dict, entry["model_name"]))

        if not candidates:
            logger.warning(
                f"Alias '{alias}' has bindings but no valid accounts found"
            )
            return None

        strategy = self._get_strategy()

        if strategy == "round_robin":
            idx = self._round_robin_index(alias, len(candidates))
            selected = candidates[idx]
        elif strategy == "random":
            selected = random.choice(candidates)
        else:  # least_conn
            selected = self._least_conn(alias, candidates)

        account_dict, model_name = selected

        # 转换为 ModelScopeAccount
        from provider.models.account import ModelScopeAccount

        ms_account = ModelScopeAccount(
            account_id=account_dict["account_id"],
            name=account_dict.get("name", ""),
            api_key=account_dict["api_key"],
            base_url=account_dict["base_url"],
        )

        logger.info(
            f"AliasRouter: routed '{alias}' → account={ms_account.account_id}, "
            f"model={model_name}, strategy={strategy}"
        )
        return RoutingResult(account=ms_account, model_name=model_name)

    def _round_robin_index(self, alias: str, size: int) -> int:
        """rr 计数器按 alias 隔离。"""
        current = self._rr_counters.get(alias, 0)
        self._rr_counters[alias] = (current + 1) % size
        return current

    def _least_conn(self, alias: str, candidates):
        """least_conn 策略：选择当前连接数最少的候选。"""
        if alias not in self._conn_counts:
            self._conn_counts[alias] = [0] * len(candidates)
        counts = self._conn_counts[alias]
        # 候选数可能变化，补齐
        while len(counts) < len(candidates):
            counts.append(0)
        min_idx = counts.index(min(counts[:len(candidates)]))
        counts[min_idx] += 1
        return candidates[min_idx]
