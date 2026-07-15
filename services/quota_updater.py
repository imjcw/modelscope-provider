import logging
from typing import Optional
from provider.repositories.quota_repository import QuotaRepository
from provider.models.account import ModelScopeAccount

logger = logging.getLogger(__name__)


class QuotaUpdater:
    """Service for updating quota information."""

    def __init__(self, quota_repository: QuotaRepository):
        self.quota_repository = quota_repository

    def update_quota_after_request(
        self,
        account: ModelScopeAccount,
        response_headers: dict,
        model_name: str
    ):
        """Update quota after receiving response from ModelScope."""
        try:
            quota_remaining = int(response_headers.get("modelscope-ratelimit-requests-remaining", 0))
            quota_limit = int(response_headers.get("modelscope-ratelimit-requests-limit", 0))
            logger.info(
                f"Updated quota for {account.account_id}: "
                f"{quota_remaining}/{quota_limit} remaining"
            )
            self.quota_repository.update_quota(
                account.account_id,
                quota_remaining,
                quota_limit
            )
            if quota_remaining == 0:
                self.quota_repository.mark_model_unavailable(account.account_id, model_name)
                logger.warning(f"Quota exhausted for {account.account_id} with model {model_name}")
        except Exception as e:
            logger.error(f"Failed to update quota: {e}")

    def get_quota_info(self, account_id: str) -> Optional[dict]:
        """Get quota information for an account."""
        return self.quota_repository.get_account_info(account_id)
