import logging
from typing import Optional
from repositories.quota_repository import QuotaRepository
from models.account import ModelScopeAccount

logger = logging.getLogger(__name__)


# 默认 header_based（被动限流）响应头名称。供应商类型可通过
# config["headers"] 覆盖这些名称，以适配不同上游的响应头约定。
DEFAULT_HEADER_BASED_CONFIG = {
    "supplier_total": "modelscope-ratelimit-requests-limit",
    "supplier_remaining": "modelscope-ratelimit-requests-remaining",
    "supplier_used": None,
    "model_total": "modelscope-ratelimit-model-requests-limit",
    "model_remaining": "modelscope-ratelimit-model-requests-remaining",
    "model_used": None,
}


def normalize_header_config(raw) -> dict:
    """合并用户提供的响应头配置与默认值，忽略未知键。"""
    cfg = dict(DEFAULT_HEADER_BASED_CONFIG)
    if isinstance(raw, dict):
        for k, v in raw.items():
            if k in cfg:
                cfg[k] = v
    return cfg


def _parse_int(value):
    """安全转换为 int，失败返回 None。"""
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


class QuotaUpdater:
    """Service for updating quota information."""

    def __init__(self, quota_repository: QuotaRepository):
        self.quota_repository = quota_repository

    def update_quota_after_request(
        self,
        account: ModelScopeAccount,
        response_headers: dict,
        model_name: str,
        header_config: dict = None,
        key_id: int = 0,
    ):
        """根据响应头更新供应商级与模型级配额。

        响应头名称可由 ``header_config``（供应商类型的 config["headers"]）
        覆盖，支持以下键（均可选，缺省为 ModelScope 原生头）：
          - supplier_total / supplier_remaining / supplier_used
          - model_total   / model_remaining   / model_used
        ``*_used`` 头用于推导 remaining = total - used。
        """
        hc = normalize_header_config(header_config)
        headers = {str(k).lower(): v for k, v in (response_headers or {}).items()}
        try:
            # 供应商级配额
            res = self._extract_quota(headers, hc, "supplier")
            if res is None:
                # 无相关响应头 → 跳过更新。上游不返回 ratelimit 头时保持已有配额值，
                # 避免每次请求都把配额清零（0/0）导致仪表盘误报“配额耗尽”。
                pass
            elif res == "invalid":
                logger.warning(
                    f"供应商配额响应头非法，跳过更新: account={account.account_id}"
                )
            else:
                quota_remaining, quota_limit = res
                self.quota_repository.update_quota(
                    account.account_id, quota_remaining, quota_limit, key_id=key_id
                )
                if quota_remaining == 0:
                    self.quota_repository.mark_model_unavailable(
                        account.account_id, model_name, key_id=key_id
                    )
                    logger.warning(
                        f"供应商配额已耗尽: {account.account_id} / model {model_name}"
                    )

            # 模型级配额
            mres = self._extract_quota(headers, hc, "model")
            if mres is None or mres == "invalid":
                # 无模型头或非法 → 跳过（保持历史行为）
                pass
            else:
                model_remaining, model_limit = mres
                if model_limit > 0:
                    self.quota_repository.update_model_quota(
                        account.account_id, model_name, model_remaining,
                        model_limit, key_id=key_id,
                    )
                    if model_remaining == 0:
                        logger.warning(
                            f"模型配额已耗尽: {account.account_id} / {model_name}"
                        )
        except Exception as e:
            logger.error(f"Failed to update quota: {e}")

    @staticmethod
    def _extract_quota(headers: dict, hc: dict, prefix: str):
        """从响应头中提取 (remaining, limit)。

        返回：
          - None              ：未找到相关响应头（供应商级应清零 / 模型级应跳过）
          - "invalid"         ：存在相关头但值无法解析（应跳过更新）
          - (remaining, limit)：成功；remaining 可由 total - used 推导
        """
        total_h = hc.get(f"{prefix}_total")
        remaining_h = hc.get(f"{prefix}_remaining")
        used_h = hc.get(f"{prefix}_used")

        total_raw = headers.get(str(total_h).lower()) if total_h else None
        remaining_raw = headers.get(str(remaining_h).lower()) if remaining_h else None
        used_raw = headers.get(str(used_h).lower()) if used_h else None

        total = _parse_int(total_raw)
        remaining = _parse_int(remaining_raw)
        used = _parse_int(used_raw)

        present = (
            (total_h is not None and total_raw is not None)
            or (remaining_h is not None and remaining_raw is not None)
            or (used_h is not None and used_raw is not None)
        )
        if not present:
            return None

        # 配置了某响应头但值无法解析 → 视为无效，跳过更新
        if (
            (total_h is not None and total_raw is not None and total is None)
            or (remaining_h is not None and remaining_raw is not None and remaining is None)
            or (used_h is not None and used_raw is not None and used is None)
        ):
            return "invalid"

        if remaining is not None:
            return (remaining, total if total is not None else 0)
        if used is not None:
            if total is None:
                return "invalid"
            return (total - used, total)
        # 仅提供 total
        return (total, total) if total is not None else (0, 0)

    def update_quota_from_usage(
        self,
        account: ModelScopeAccount,
        input_tokens: int,
        output_tokens: int,
        model_name: str,
        key_id: int = 0,
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
                model_name,
                key_id=key_id,
            )
            # Also record model-level usage
            self.quota_repository.record_model_usage(
                account.account_id,
                model_name,
                input_tokens,
                output_tokens,
                key_id=key_id,
            )
        except Exception as e:
            logger.error(f"Failed to update quota from usage: {e}")

    def get_quota_info(self, account_id: str) -> Optional[dict]:
        """Get quota information for an account."""
        return self.quota_repository.get_account_info(account_id)
