"""AliasRouter — 根据虚拟模型ID的绑定条目选择路由。"""
import logging
import random
from dataclasses import dataclass
from typing import List, Optional

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

    def __init__(self, mapping_model_repo, account_repo, config_repo=None, config_cache=None):
        self.mapping_model_repo = mapping_model_repo
        self.account_repo = account_repo
        self.config_repo = config_repo
        self.config_cache = config_cache
        # round_robin 计数器按 alias 隔离
        self._rr_counters = {}
        # least_conn 策略的每条目请求计数
        self._conn_counts = {}

    def _get_strategy(self) -> str:
        """从缓存（优先）或 DB 读取策略，默认 round_robin。"""
        # 优先使用内存缓存（避免每次请求查 DB）
        if self.config_cache is not None:
            val = self.config_cache.get("load_balancer_strategy")
            if val in ("round_robin", "least_conn", "random"):
                return val
            return "round_robin"
        # 保底：从 DB 读取
        if self.config_repo is not None:
            val = self.config_repo.get("load_balancer_strategy")
            if val in ("round_robin", "least_conn", "random"):
                return val
        return "round_robin"

    def _build_candidates(self, alias: str) -> List[tuple]:
        """解析 alias 的所有绑定条目，返回 (account_dict, model_name) 候选列表。

        自动过滤失效绑定（is_valid=0），即该供应商的 supplier_models 中
        已不存在对应模型名的行。
        """
        entries = self.mapping_model_repo.find_by_alias(alias)
        if not entries:
            return []

        # 过滤失效绑定
        valid_entries = [e for e in entries if e.get("is_valid", 1) == 1]
        if not valid_entries:
            logger.warning("Alias '%s' has %d bindings but none are valid",
                           alias, len(entries))
            return []

        # 批量查询账户：收集所有唯一的 supplier_id，一次查询获取所有账户
        supplier_ids = list({entry["supplier_id"] for entry in valid_entries})
        accounts_by_id = self.account_repo.find_by_ids(supplier_ids)

        candidates = []
        for entry in valid_entries:
            account_dict = accounts_by_id.get(entry["supplier_id"])
            if account_dict:
                candidates.append((account_dict, entry["model_name"]))

        return candidates

    def _to_ms_account(self, account_dict: dict) -> object:
        """将 account dict 转换为 ModelScopeAccount。"""
        from models.account import ModelScopeAccount, DEFAULT_PROVIDER_TYPE
        return ModelScopeAccount(
            account_id=account_dict["account_id"],
            name=account_dict.get("name", ""),
            api_key=account_dict["api_key"],
            base_url=account_dict["base_url"],
            provider_type=account_dict.get("provider_type", DEFAULT_PROVIDER_TYPE),
        )

    def get_candidates(self, alias: str) -> List[RoutingResult]:
        """返回 alias 的所有可用候选路由，按策略排序。

        与 route() 不同，此方法返回所有候选而非只选一个，
        调用方可在失败时尝试下一个候选。

        Returns:
            按策略排序的 RoutingResult 列表（可能为空）。
        """
        candidates = self._build_candidates(alias)
        if not candidates:
            return []

        strategy = self._get_strategy()

        if strategy == "round_robin":
            # 从当前轮询位置开始，取所有候选
            idx = self._round_robin_index(alias, len(candidates))
            # 重排：从 idx 开始，循环取完所有
            ordered = candidates[idx:] + candidates[:idx]
        elif strategy == "random":
            ordered = candidates.copy()
            random.shuffle(ordered)
        else:  # least_conn — 按连接数升序排列
            counts = self._get_conn_counts(alias, len(candidates))
            ordered = [c for _, c in sorted(zip(counts, candidates))]
            # 递增第一个候选的连接数（模拟选中）
            first_idx = candidates.index(ordered[0])
            counts[first_idx] += 1

        results = []
        for account_dict, model_name in ordered:
            ms_account = self._to_ms_account(account_dict)
            results.append(RoutingResult(account=ms_account, model_name=model_name))

        logger.info(
            f"AliasRouter: got {len(results)} candidates for '{alias}', "
            f"strategy={strategy}"
        )
        return results

    def route(self, alias: str) -> Optional[RoutingResult]:
        """为 alias 选择一个绑定条目。

        Returns:
            RoutingResult（有绑定时）或 None（无绑定时）
        """
        candidates = self._build_candidates(alias)
        if not candidates:
            return None

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
        ms_account = self._to_ms_account(account_dict)

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
        counts = self._get_conn_counts(alias, len(candidates))
        min_idx = counts.index(min(counts[:len(candidates)]))
        counts[min_idx] += 1
        return candidates[min_idx]

    def _get_conn_counts(self, alias: str, size: int) -> list:
        """获取或初始化 least_conn 计数数组。"""
        if alias not in self._conn_counts:
            self._conn_counts[alias] = [0] * size
        while len(self._conn_counts[alias]) < size:
            self._conn_counts[alias].append(0)
        return self._conn_counts[alias]
