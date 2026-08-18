"""供应商限流策略工厂。"""

from services.providers.base import RateLimitStrategy
from services.providers.modelscope import ModelScopeStrategy
from services.providers.sensetime import SenseTimeStrategy
from services.providers.per_model import PerModelFixedWindowStrategy

_STRATEGY_MAP = {
    # 按策略种类（strategy_type）注册——供应商类型管理以此选择限流行为
    "header_based": ModelScopeStrategy,
    "fixed_window": SenseTimeStrategy,
    "fixed_window_per_model": PerModelFixedWindowStrategy,
    # 兼容旧调用（按供应商类型 key 直接创建）
    "modelscope": ModelScopeStrategy,
    "sensetime": SenseTimeStrategy,
}


def create_strategy(provider_type: str, **kwargs) -> RateLimitStrategy:
    """Create a rate-limit strategy for the given strategy type / provider type.

    Args:
        provider_type: A registered strategy type ("header_based" / "fixed_window")
            or a legacy provider key ("modelscope" / "sensetime").
        **kwargs: Provider-specific dependencies passed to the strategy constructor.

    Raises:
        ValueError: If provider_type is not registered.
    """
    cls = _STRATEGY_MAP.get(provider_type)
    if cls is None:
        raise ValueError(f"Unknown provider_type: {provider_type}")
    return cls(**kwargs)


__all__ = [
    "RateLimitStrategy",
    "ModelScopeStrategy",
    "SenseTimeStrategy",
    "PerModelFixedWindowStrategy",
    "create_strategy",
    "build_rate_limit_strategies",
]


def build_rate_limit_strategies(provider_types, db, quota_updater, quota_repository,
                                rate_limit_cache=None) -> dict:
    """按供应商类型列表构建 {type_key: RateLimitStrategy} 字典。

    每个供应商类型由其 strategy_type 决定限流行为，config 提供策略参数：
      - header_based → ModelScopeStrategy（被动式，依赖上游响应头）
      - fixed_window → SenseTimeStrategy（主动式固定窗口，window_seconds / max_requests）
    未知 strategy_type 回退到 header_based（最宽松，不主动拦截）。
    """
    strategies: dict = {}
    for pt in provider_types or []:
        type_key = pt.get("type_key")
        if not type_key:
            continue
        cfg = pt.get("config") or {}
        stype = pt.get("strategy_type") or "header_based"
        if stype in ("fixed_window", "sensetime"):
            strategies[type_key] = create_strategy(
                "fixed_window",
                db=db,
                window_seconds=int(cfg.get("window_seconds", 18000)),
                max_requests=int(cfg.get("max_requests", 1500)),
                rate_limit_cache=rate_limit_cache,
            )
        elif stype == "fixed_window_per_model":
            model_configs = cfg.get("models", {})
            strategies[type_key] = create_strategy(
                "fixed_window_per_model",
                db=db,
                window_seconds=int(cfg.get("window_seconds", 18000)),
                max_requests=int(cfg.get("max_requests", 1500)),
                model_configs=model_configs,
                rate_limit_cache=rate_limit_cache,
            )
        else:
            # header_based（被动限流）：响应头名称可由 provider type 的
            # config["headers"] 覆盖，未配置时使用默认 ModelScope 头。
            strategies[type_key] = create_strategy(
                "header_based",
                quota_updater=quota_updater,
                quota_repository=quota_repository,
                header_config=cfg.get("headers") if isinstance(cfg, dict) else None,
            )
    return strategies
