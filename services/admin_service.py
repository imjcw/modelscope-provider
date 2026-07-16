"""Admin service for the management panel."""
import uuid

from provider.repositories.account_repository import AccountRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.log_repository import LogRepository


class AdminService:
    """High-level admin operations."""

    def __init__(self, account_repo: AccountRepository,
                 mapping_repo: MappingRepository,
                 config_repo: ConfigRepository,
                 log_repo: LogRepository):
        self.account_repo = account_repo
        self.mapping_repo = mapping_repo
        self.config_repo = config_repo
        self.log_repo = log_repo

    # ── Accounts ──

    def get_accounts(self):
        return self.account_repo.find_all()

    def get_account(self, account_id: int):
        return self.account_repo.find_by_id(account_id)

    def create_account(self, account_id: str, api_key: str,
                       base_url: str, region: str = "china") -> dict:
        return self.account_repo.create(account_id, api_key, base_url, region)

    def update_account(self, account_id: int, **kwargs) -> dict:
        return self.account_repo.update(account_id, **kwargs)

    def delete_account(self, account_id: int) -> bool:
        return self.account_repo.delete(account_id)

    def toggle_account(self, account_id: int) -> dict:
        account = self.account_repo.find_by_id(account_id)
        if not account:
            return None
        new_status = "disabled" if account["status"] == "active" else "active"
        return self.account_repo.update(account_id, status=new_status)

    # ── Mappings ──

    def get_mappings(self):
        return self.mapping_repo.find_all()

    def get_mappings_by_alias(self, alias_name: str):
        return self.mapping_repo.find_by_alias(alias_name)

    def upsert_mapping(self, alias_name: str, region: str, actual_model_id: str):
        return self.mapping_repo.create(alias_name, region, actual_model_id)

    def bulk_update_mappings(self, mappings: dict):
        self.mapping_repo.bulk_upsert(mappings)

    def delete_mapping(self, alias_name: str):
        return self.mapping_repo.delete_by_alias(alias_name)

    # ── Config ──

    def get_config(self) -> dict:
        return self.config_repo.get_all()

    def set_config(self, key: str, value: str):
        self.config_repo.set(key, value)

    def bulk_set_config(self, config: dict):
        self.config_repo.bulk_set(config)

    # ── Logs ──

    def get_logs(self, page: int = 0, page_size: int = 50, **filters):
        return self.log_repo.find_all(page=page, page_size=page_size, **filters)

    def get_log_detail(self, log_id: int):
        return self.log_repo.find_by_id(log_id)

    def log_request(self, model: str, actual_model_id: str = None,
                    account_id: str = None, status_code: int = None,
                    input_tokens: int = 0, output_tokens: int = 0,
                    latency_ms: int = None, is_stream: bool = False,
                    error_message: str = None, raw_request: str = None,
                    raw_response: str = None) -> str:
        """Log a request and return its request_id."""
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        self.log_repo.create(
            request_id=request_id, model=model, actual_model_id=actual_model_id,
            account_id=account_id, status_code=status_code,
            input_tokens=input_tokens, output_tokens=output_tokens,
            latency_ms=latency_ms, is_stream=is_stream,
            error_message=error_message, raw_request=raw_request,
            raw_response=raw_response,
        )
        return request_id

    # ── Stats ──

    def get_stats(self, days: int = 30):
        """Aggregate statistics for the given period."""
        from collections import defaultdict
        from datetime import datetime, timedelta

        with self.log_repo.db.get_connection() as conn:
            conn.row_factory = conn.row_factory or self.log_repo.db.get_connection().__enter__().row_factory

        records = []
        page = 0
        while True:
            batch, total = self.get_logs(page=page, page_size=500)
            records.extend(batch)
            if len(records) >= total:
                break
            page += 1

        # Heatmap: count by (weekday, hour)
        heatmap = defaultdict(int)
        # Daily token trend: {date: {model: input_tokens + output_tokens}}
        daily_tokens = defaultdict(lambda: defaultdict(int))
        # Model usage: {model: tokens}
        model_usage = defaultdict(int)

        for r in records:
            ts = r.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    heatmap[(dt.weekday(), dt.hour)] += 1
                    date_str = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    continue

            tokens = (r.get("input_tokens", 0) or 0) + (r.get("output_tokens", 0) or 0)
            if r.get("model"):
                model_usage[r["model"]] += tokens
            if ts:
                daily_tokens[date_str][r.get("model", "unknown")] += tokens

        return {
            "heatmap": {f"{w},{h}": c for (w, h), c in heatmap.items()},
            "daily_tokens": {d: dict(m) for d, m in daily_tokens.items()},
            "model_usage": dict(model_usage),
            "total_requests": len(records),
        }
