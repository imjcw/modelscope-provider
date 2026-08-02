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
