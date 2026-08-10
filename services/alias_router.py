"""AliasRouter — 根据虚拟模型ID的绑定条目选择路由。"""
import logging
import random
import threading
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """路由结果：选中的账户 + 实际模型名 + 具体 API Key。

    ``key_id`` 是 ``account_api_keys.id``（0 = 主密钥），``key_string``
    是实际 API Key 明文，由 HttpClient 直接使用（不再内部轮换）。
    """

    account: object       # ModelScopeAccount 实例
    model_name: str       # 直接发给下游的模型名
    key_id: int = 0       # account_api_keys.id；0 表示主密钥（accounts 表）
    key_string: str = ""  # 实际用于 HTTP 请求的 API Key 字符串


class AliasRouter:
    """根据虚拟模型ID的绑定条目选择路由，每个活跃 API Key 独立为一个候选。

    ``_build_candidates`` 会把每个 ``(绑定条目, 活跃 Key)`` 展开为一个独立候选，
    因此：
    - 账号 A 有 3 个 Key、账号 B 有 2 个 Key → 共 5 个候选
    - 负载均衡策略（round_robin/least_conn/random）在 Key 粒度上生效
    - 熔断器按 ``(key_id, model)`` 冻结，一个 Key 失败不影响同账号其他 Key

    候选过滤会排除：
    - 失效绑定（``is_valid=0``）
    - 已禁用账号（``status != 'active'``）
    - 冻结状态的 Key（``status == 'frozen'``）
    - 配额耗尽的模型（``unavailable_models``）
    """

    def __init__(
        self,
        mapping_model_repo,
        account_repo,
        config_repo=None,
        config_cache=None,
        quota_repository=None,
    ):
        self.mapping_model_repo = mapping_model_repo
        self.account_repo = account_repo
        self.config_repo = config_repo
        self.config_cache = config_cache
        self.quota_repository = quota_repository
        # round_robin 计数器按 alias 隔离
        self._rr_counters: Dict[str, int] = {}
        # least_conn 策略的在途连接计数，按 (key_id, model_name) 身份隔离
        self._conn_counts: Dict[Tuple[int, str], int] = {}
        self._lock = threading.Lock()

    def _get_strategy(self) -> str:
        """从缓存（优先）或 DB 读取策略，默认 round_robin。"""
        if self.config_cache is not None:
            val = self.config_cache.get("load_balancer_strategy")
            if val in ("round_robin", "least_conn", "random"):
                return val
            return "round_robin"
        if self.config_repo is not None:
            val = self.config_repo.get("load_balancer_strategy")
            if val in ("round_robin", "least_conn", "random"):
                return val
        return "round_robin"

    def _build_candidates(self, alias: str) -> List[tuple]:
        """解析 alias 的所有绑定条目，返回 ``(account_dict, model_name, key_record)``
        候选列表——每个活跃 Key 独立一个候选。

        过滤：失效绑定、禁用账号、冻结 Key、配额耗尽模型。
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

        # 批量查询账户
        supplier_ids = list({entry["supplier_id"] for entry in valid_entries})
        accounts_by_id = self.account_repo.find_by_ids(supplier_ids)

        # 批量查询配额耗尽模型
        unavailable_map = self._load_unavailable_models(accounts_by_id)

        # 批量查询多 API Key
        keys_by_id = self._load_api_keys(supplier_ids)

        # 回填多 Key 记录到 account dict，使 _to_ms_account 能产出带
        # api_key_records 的 ModelScopeAccount（供 HttpClient 多 Key 轮换）。
        # 旧实现读了一个从不存在的 "_api_key_records" 键，导致恒为 None（M2）。
        for _sid, _acc in accounts_by_id.items():
            _acc["api_key_records"] = keys_by_id.get(_sid)

        candidates = []
        for entry in valid_entries:
            account_dict = accounts_by_id.get(entry["supplier_id"])
            if not account_dict:
                continue
            # 跳过已禁用账号
            if account_dict.get("status", "active") != "active":
                continue
            model_name = entry["model_name"]
            # 跳过配额耗尽的模型
            if model_name in unavailable_map.get(account_dict["account_id"], set()):
                continue

            # 获取该账号的 Key 记录（全部来自 account_api_keys 表）
            key_records = keys_by_id.get(entry["supplier_id"])
            if not key_records:
                # 没有 account_api_keys 记录 → 该账号无可用 Key，跳过
                # （accounts.api_key 列已废弃并删除，主键统一存于 account_api_keys）
                continue

            # 每个活跃 Key 展开为一个独立候选
            for kr in key_records:
                if kr.get("status") == "frozen":
                    continue
                candidates.append((account_dict, model_name, kr))

        return candidates

    def _load_unavailable_models(self, accounts_by_id: Dict[int, dict]) -> Dict[str, set]:
        """批量读取各账号当日 unavailable_models。"""
        if self.quota_repository is None or not accounts_by_id:
            return {}
        getter = getattr(self.quota_repository, "get_unavailable_models_batch", None)
        if getter is None:
            return {}
        acc_str_ids = [a["account_id"] for a in accounts_by_id.values()]
        try:
            return getter(acc_str_ids) or {}
        except Exception:
            logger.warning("Failed to load unavailable_models batch", exc_info=True)
            return {}

    def _load_api_keys(self, supplier_ids: List[int]) -> Dict[int, list]:
        """批量读取各账号的 API Key 记录。"""
        if not supplier_ids:
            return {}
        getter = getattr(self.account_repo, "find_api_keys_by_account_ids", None)
        if getter is None:
            return {}
        try:
            return getter(supplier_ids) or {}
        except Exception:
            logger.warning("Failed to load api keys batch", exc_info=True)
            return {}

    def _to_ms_account(self, account_dict: dict) -> "ModelScopeAccount":
        """将 account dict 转换为 ModelScopeAccount（含多 API Key 记录）。

        api_key_records 由 _build_candidates 在批量加载 keys 后回填到
        account_dict，因此这里能拿到真实的多 Key 记录（旧实现读了从不存在的
        ``_api_key_records`` 键，导致恒为 None；见 M2）。
        """
        from models.account import build_ms_account
        return build_ms_account(
            account_dict,
            api_key_records=account_dict.get("api_key_records"),
        )

    def get_candidates(self, alias: str) -> List[RoutingResult]:
        """返回 alias 的所有可用候选路由，按策略排序。

        每个候选对应一个 ``(账号, 模型, Key)`` 三元组。least_conn 策略按
        当前在途连接数（``acquire/release`` 维护）升序排列。

        Returns:
            按策略排序的 RoutingResult 列表（可能为空）。
        """
        candidates = self._build_candidates(alias)
        if not candidates:
            return []

        strategy = self._get_strategy()

        if strategy == "round_robin":
            idx = self._round_robin_index(alias, len(candidates))
            ordered = candidates[idx:] + candidates[:idx]
        elif strategy == "random":
            ordered = candidates.copy()
            random.shuffle(ordered)
        else:  # least_conn
            ordered = sorted(
                candidates,
                key=lambda c: self._conn_count(self._identity(c)),
            )

        results = []
        for account_dict, model_name, key_record in ordered:
            ms_account = self._to_ms_account(account_dict)
            results.append(RoutingResult(
                account=ms_account,
                model_name=model_name,
                key_id=key_record["id"],
                key_string=key_record["api_key"],
            ))

        logger.info(
            f"AliasRouter: got {len(results)} key-level candidates for '{alias}', "
            f"strategy={strategy}"
        )
        return results

    def route(self, alias: str) -> Optional[RoutingResult]:
        """为 alias 选择一个（账号, 模型, Key）三元组。

        复用 :meth:`get_candidates` 的排序逻辑（round_robin/random/least_conn），
        避免与候选构建逻辑重复（M8）。least_conn 下 get_candidates 已将候选按在途
        连接数升序排列，取首位即最低负载；为保持与原 route 语义一致，仅在
        least_conn 时对选中的候选 acquire（release 由调用方负责）。

        Returns:
            RoutingResult（有绑定时）或 None（无绑定时）
        """
        candidates = self.get_candidates(alias)
        if not candidates:
            return None

        selected = candidates[0]  # get_candidates 已按策略排序
        strategy = self._get_strategy()
        if strategy == "least_conn":
            # 递增在途连接计数，与原 route() 的 least_conn 分支语义一致
            self.acquire(selected.key_id, selected.model_name)

        logger.info(
            f"AliasRouter: routed '{alias}' → account={selected.account.account_id}, "
            f"key_id={selected.key_id}, model={selected.model_name}, strategy={strategy}"
        )
        return selected
        return RoutingResult(
            account=ms_account,
            model_name=model_name,
            key_id=key_record["id"],
            key_string=key_record["api_key"],
        )

    # ----- least_conn 在途连接计数 -----------------------------------------

    @staticmethod
    def _identity(candidate: tuple) -> Tuple[int, str]:
        """候选的身份键 ``(key_id, model_name)``。"""
        _account_dict, model_name, key_record = candidate
        return (key_record["id"], model_name)

    def _conn_count(self, key: Tuple[int, str]) -> int:
        with self._lock:
            return self._conn_counts.get(key, 0)

    def acquire(self, key_id: int, model_name: str) -> None:
        """候选被实际派发时调用：在途连接数 +1。"""
        with self._lock:
            key = (key_id, model_name)
            self._conn_counts[key] = self._conn_counts.get(key, 0) + 1

    def release(self, key_id: int, model_name: str) -> None:
        """请求完成（成功或失败）时调用：在途连接数 -1（不低于 0）。"""
        with self._lock:
            key = (key_id, model_name)
            current = self._conn_counts.get(key, 0)
            if current <= 1:
                self._conn_counts.pop(key, None)
            else:
                self._conn_counts[key] = current - 1

    def _round_robin_index(self, alias: str, size: int) -> int:
        """rr 计数器按 alias 隔离。"""
        with self._lock:
            current = self._rr_counters.get(alias, 0)
            self._rr_counters[alias] = (current + 1) % size
            return current