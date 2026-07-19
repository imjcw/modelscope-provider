import logging
from typing import Optional
from repositories.quota_repository import QuotaRepository
from models.account import ModelScopeAccount

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
        """Update both supplier-level and model-level quota from response headers.

        Supplier-level: modelscope-ratelimit-requests-{limit,remaining}
        Model-level:    modelscope-ratelimit-model-requests-{limit,remaining}
        """
        try:
            # Supplier-level quota
            quota_remaining = int(response_headers.get("modelscope-ratelimit-requests-remaining", 0))
            quota_limit = int(response_headers.get("modelscope-ratelimit-requests-limit", 0))
            logger.info(
                f"Updated supplier quota for {account.account_id}: "
                f"{quota_remaining}/{quota_limit} remaining"
            )
            self.quota_repository.update_quota(
                account.account_id,
                quota_remaining,
                quota_limit
            )
            if quota_remaining == 0:
                self.quota_repository.mark_model_unavailable(account.account_id, model_name)
                logger.warning(f"Supplier quota exhausted for {account.account_id} with model {model_name}")

            # Model-level quota
            model_remaining = int(response_headers.get("modelscope-ratelimit-model-requests-remaining", 0))
            model_limit = int(response_headers.get("modelscope-ratelimit-model-requests-limit", 0))
            if model_limit > 0:
                logger.info(
                    f"Updated model quota for {account.account_id}/{model_name}: "
                    f"{model_remaining}/{model_limit} remaining"
                )
                self.quota_repository.update_model_quota(
                    account.account_id,
                    model_name,
                    model_remaining,
                    model_limit
                )
                if model_remaining == 0:
                    logger.warning(f"Model quota exhausted for {account.account_id}/{model_name}")
        except Exception as e:
            logger.error(f"Failed to update quota: {e}")

    def update_quota_from_usage(
        self,
        account: ModelScopeAccount,
        input_tokens: int,
        output_tokens: int,
        model_name: str
    ):
        """Update both supplier-level and model-level token usage tracking.

        This is used when HTTP response headers (rate-limit headers) are
        not available — e.g. for streaming SSE responses. We track token
        consumption per request so the admin panel can show usage derived
        from request logs.
        """
        try:
            total_used = input_tokens + output_tokens
            logger.info(
                f"Tracked usage for {account.account_id}: "
                f"in={input_tokens}, out={output_tokens}, total={total_used}"
            )
            # We don't have a hard quota_limit from headers, so we only
            # record the usage. The admin panel will aggregate from logs.
            self.quota_repository.record_usage(
                account.account_id,
                input_tokens,
                output_tokens,
                model_name
            )
            # Also record model-level usage
            self.quota_repository.record_model_usage(
                account.account_id,
                model_name,
                input_tokens,
                output_tokens
            )
        except Exception as e:
            logger.error(f"Failed to update quota from usage: {e}")

    def get_quota_info(self, account_id: str) -> Optional[dict]:
        """Get quota information for an account."""
        return self.quota_repository.get_account_info(account_id)
