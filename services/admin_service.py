"""Admin service for the management panel."""
import uuid

from provider.repositories.account_repository import AccountRepository
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.log_repository import LogRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.repositories.quota_repository import QuotaRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository


class AdminService:
    """High-level admin operations."""

    def __init__(self, account_repo: AccountRepository,
                 mapping_repo: MappingRepository,
                 config_repo: ConfigRepository,
                 log_repo: LogRepository,
                 quota_repo: QuotaRepository = None,
                 supplier_model_repo: SupplierModelRepository = None):
        self.account_repo = account_repo
        self.mapping_repo = mapping_repo
        self.config_repo = config_repo
        self.log_repo = log_repo
        self.quota_repo = quota_repo
        self.supplier_model_repo = supplier_model_repo

    # ── Accounts ──

    def get_accounts(self):
        """List accounts enriched with today's quota info (when quota_repo set)."""
        accounts = self.account_repo.find_all()
        if self.quota_repo is not None:
            for acc in accounts:
                info = self.quota_repo.get_account_info(acc["account_id"])
                if info:
                    acc["quota_remaining"] = info["quota_remaining"]
                    acc["quota_limit"] = info["quota_limit"]
                else:
                    acc["quota_remaining"] = 0
                    acc["quota_limit"] = 0
        else:
            for acc in accounts:
                acc.setdefault("quota_remaining", 0)
                acc.setdefault("quota_limit", 0)
        return accounts

    def get_account(self, account_id: int):
        acc = self.account_repo.find_by_id(account_id)
        if acc and self.quota_repo is not None:
            info = self.quota_repo.get_account_info(acc["account_id"])
            if info:
                acc["quota_remaining"] = info["quota_remaining"]
                acc["quota_limit"] = info["quota_limit"]
            else:
                acc["quota_remaining"] = 0
                acc["quota_limit"] = 0
        elif acc:
            acc.setdefault("quota_remaining", 0)
            acc.setdefault("quota_limit", 0)
        return acc

    def create_account(self, name: str, api_key: str,
                       base_url: str, region: str = "china") -> dict:
        return self.account_repo.create(name, api_key, base_url, region)

    def update_account(self, account_id: int, **kwargs) -> dict:
        return self.account_repo.update(account_id, **kwargs)

    def delete_account(self, account_id: int) -> bool:
        if self.supplier_model_repo is not None:
            self.supplier_model_repo.delete_by_supplier(account_id)
        return self.account_repo.delete(account_id)

    def toggle_account(self, account_id: int) -> dict:
        account = self.account_repo.find_by_id(account_id)
        if not account:
            return None
        new_status = "disabled" if account["status"] == "active" else "active"
        return self.account_repo.update(account_id, status=new_status)

    # ── Supplier Models ──

    def get_supplier_models(self, supplier_id: int):
        if self.supplier_model_repo is None:
            return []
        return self.supplier_model_repo.find_by_supplier(supplier_id)

    def create_supplier_model(self, supplier_id: int,
                              model_name: str, model_type: str,
                              context_length: int = None) -> dict:
        if self.supplier_model_repo is None:
            raise NotImplementedError("Supplier model repo not configured")
        return self.supplier_model_repo.create(
            supplier_id, model_name, model_type, context_length
        )

    def delete_supplier_model(self, model_id: int) -> bool:
        if self.supplier_model_repo is None:
            return False
        return self.supplier_model_repo.delete(model_id)

    def bulk_set_supplier_models(self, supplier_id: int,
                                 models: list) -> list:
        if self.supplier_model_repo is None:
            return []
        self.supplier_model_repo.bulk_upsert(supplier_id, models)
        return self.supplier_model_repo.find_by_supplier(supplier_id)

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
                    account_id: str = None, account_name: str = None,
                    status_code: int = None,
                    input_tokens: int = 0, output_tokens: int = 0,
                    latency_ms: int = None, is_stream: bool = False,
                    error_message: str = None, raw_request: str = None,
                    raw_response: str = None) -> str:
        """Log a request and return its request_id."""
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        self.log_repo.create(
            request_id=request_id, model=model, actual_model_id=actual_model_id,
            account_id=account_id, account_name=account_name, status_code=status_code,
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
