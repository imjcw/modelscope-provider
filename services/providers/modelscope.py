"""ModelScope 限流策略：被动式，依赖上游响应头。"""

import logging
from typing import Optional

from models.account import ModelScopeAccount
from repositories.quota_repository import QuotaRepository
from services.providers.base import RateLimitStrategy
from services.quota_updater import QuotaUpdater

logger = logging.getLogger(__name__)


class ModelScopeStrategy(RateLimitStrategy):
    """ModelScope rate-limit strategy.

    Reactive model: quota exhaustion is discovered from upstream 429
    responses and modelscope-ratelimit-* headers. Pre-request checks
    always pass; post-request recording parses headers.
    """

    def __init__(
        self,
        quota_updater: QuotaUpdater,
        quota_repository: QuotaRepository,
        header_config: dict = None,
    ):
        self.quota_updater = quota_updater
        self.quota_repository = quota_repository
        # 供应商类型可配置的响应头名称（None 表示使用默认 ModelScope 头）
        self.header_config = header_config

    # 仅瞬态错误触发标记 unavailable；auth_error 和 bad_request 属于
    # 密钥/配置问题，不应标记模型不可用。
    _TRANSIENT_ERROR_TYPES = {"server_error", "timeout", "network_error", "rate_limited"}

    def on_circuit_breaker_escalation(
        self,
        account_id: str,
        model_name: str,
        error_type: Optional[str],
    ) -> None:
        """熔断升级：连续 10 次瞬态失败后，标记模型今日不可用，
        让路由直接跳过该候选，而不是等 1 小时冻结窗口过去再试。
        """
        if error_type not in self._TRANSIENT_ERROR_TYPES:
            logger.debug(
                "Circuit-breaker escalation skipped (non-transient error): "
                "%s/%s error_type=%s",
                account_id, model_name, error_type,
            )
            return
        logger.warning(
            "Circuit-breaker escalation: marking %s/%s unavailable (error_type=%s)",
            account_id, model_name, error_type,
        )
        self.quota_repository.mark_model_unavailable(account_id, model_name)

    def check_rate_limit(self, account_id: str, model_name: str, key_count: int = 1) -> bool:
        """Always allow — ModelScope quota is enforced upstream."""
        return True

    def record_request(
        self,
        account_id: str,
        model_name: str,
        response_headers: dict,
        status_code: int,
    ) -> None:
        """Parse modelscope-ratelimit-* headers and update quota tables."""
        account = ModelScopeAccount(
            account_id=account_id,
            api_key="",
            base_url="",
        )
        self.quota_updater.update_quota_after_request(
            account, response_headers, model_name, self.header_config
        )

    def record_usage(
        self,
        account_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record token usage from streaming responses."""
        account = ModelScopeAccount(
            account_id=account_id,
            api_key="",
            base_url="",
        )
        self.quota_updater.update_quota_from_usage(
            account, input_tokens, output_tokens, model_name
        )

    def get_quota_info(self, account_id: str) -> dict:
        """Read today's quota from the account_quotas table."""
        info = self.quota_repository.get_account_info(account_id)
        if info:
            return {
                "quota_remaining": info.get("quota_remaining", 0),
                "quota_limit": info.get("quota_limit", 0),
            }
        return {"quota_remaining": 0, "quota_limit": 0}
