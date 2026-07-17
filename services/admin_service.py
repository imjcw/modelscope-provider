"""Admin service for the management panel."""
import uuid

from provider.repositories.account_repository import AccountRepository
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.log_repository import LogRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.repositories.mapping_model_repository import MappingModelRepository
from provider.repositories.quota_repository import QuotaRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository


class AdminService:
    """High-level admin operations."""

    def __init__(self, account_repo: AccountRepository,
                 mapping_repo: MappingRepository,
                 config_repo: ConfigRepository,
                 log_repo: LogRepository,
                 quota_repo: QuotaRepository = None,
                 supplier_model_repo: SupplierModelRepository = None,
                 mapping_model_repo: MappingModelRepository = None):
        self.account_repo = account_repo
        self.mapping_repo = mapping_repo
        self.config_repo = config_repo
        self.log_repo = log_repo
        self.quota_repo = quota_repo
        self.supplier_model_repo = supplier_model_repo
        self.mapping_model_repo = mapping_model_repo

    # ── Accounts ──

    def get_suppliers(self):
        """List suppliers enriched with today's quota info (when quota_repo set)."""
        suppliers = self.account_repo.find_all()
        if self.quota_repo is not None:
            for s in suppliers:
                info = self.quota_repo.get_account_info(s["account_id"])
                if info:
                    s["quota_remaining"] = info["quota_remaining"]
                    s["quota_limit"] = info["quota_limit"]
                else:
                    s["quota_remaining"] = 0
                    s["quota_limit"] = 0
        else:
            for s in suppliers:
                s.setdefault("quota_remaining", 0)
                s.setdefault("quota_limit", 0)
        return suppliers

    def get_supplier(self, supplier_id: int):
        s = self.account_repo.find_by_id(supplier_id)
        if s and self.quota_repo is not None:
            info = self.quota_repo.get_account_info(s["account_id"])
            if info:
                s["quota_remaining"] = info["quota_remaining"]
                s["quota_limit"] = info["quota_limit"]
            else:
                s["quota_remaining"] = 0
                s["quota_limit"] = 0
        elif s:
            s.setdefault("quota_remaining", 0)
            s.setdefault("quota_limit", 0)
        return s

    def create_supplier(self, name: str, api_key: str,
                        base_url: str) -> dict:
        return self.account_repo.create(name, api_key, base_url)

    def update_supplier(self, supplier_id: int, **kwargs) -> dict:
        return self.account_repo.update(supplier_id, **kwargs)

    def delete_supplier(self, supplier_id: int) -> bool:
        if self.supplier_model_repo is not None:
            self.supplier_model_repo.delete_by_supplier(supplier_id)
        return self.account_repo.delete(supplier_id)

    def toggle_supplier(self, supplier_id: int) -> dict:
        s = self.account_repo.find_by_id(supplier_id)
        if not s:
            return None
        new_status = "disabled" if s["status"] == "active" else "active"
        return self.account_repo.update(supplier_id, status=new_status)

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

    def upsert_mapping(self, alias_name: str, actual_model_id: str):
        return self.mapping_repo.create(alias_name, actual_model_id)

    def bulk_update_mappings(self, mappings: dict):
        self.mapping_repo.bulk_upsert(mappings)

    def delete_mapping(self, alias_name: str):
        return self.mapping_repo.delete_by_alias(alias_name)

    def resolve_mapping_alias(self, alias: str) -> str:
        """Resolve mapping alias to actual model ID with multi-model support.

        Returns:
            actual_model_id: The selected model name from bound suppliers

        Raises:
            ValueError: If no models are bound to this alias
        """
        if self.mapping_model_repo is None:
            raise ValueError("Mapping model repo not configured")

        # Fetch all models bound to this alias
        model_entries = self.mapping_model_repo.find_by_alias(alias)

        if not model_entries:
            raise ValueError(f"No models bound to alias '{alias}'")

        # Build a list of accounts for load balancing
        accounts_for_alias = []
        for entry in model_entries:
            accounts_for_alias.append(
                type('Account', (), {
                    'account_id': f'mapping_{entry["id"]}',
                    'base_url': '',  # Will be filled below
                    'model_name': entry['model_name'],
                    'actual_model_id': entry['model_name'],
                    'current_index': 0,
                })()
            )

        # Fetch supplier details for all suppliers in the mapping
        supplier_ids = {entry['supplier_id'] for entry in model_entries}
        supplier_details = {}
        for sid in supplier_ids:
            sup = self.account_repo.find_by_id(sid)
            if sup:
                supplier_details[sid] = sup

        if not supplier_details:
            raise ValueError(f"Cannot find supplier details for alias '{alias}'")

        # Use the first supplier's base_url for all accounts (they're the same supplier)
        base_url = next(iter(supplier_details.values()))['base_url']

        # Override base_url for all accounts
        for acc in accounts_for_alias:
            acc.base_url = base_url

        # Select account using load balancer
        from provider.services.load_balancer import LoadBalancer
        load_balancer = LoadBalancer(accounts_for_alias)
        selected = load_balancer.select_account(model_name=model_entries[0]['model_name'])

        return selected.actual_model_id

    def get_mapping_models(self, alias_name: str):
        """Get all models bound to a mapping alias."""
        if self.mapping_model_repo is None:
            return []
        return self.mapping_model_repo.find_by_alias(alias_name)

    def add_mapping_model(self, alias_name: str, supplier_id: int, model_name: str):
        """Add a model to a mapping alias."""
        if self.mapping_model_repo is None:
            raise NotImplementedError("Mapping model repo not configured")
        return self.mapping_model_repo.add_model(alias_name, supplier_id, model_name)

    def remove_mapping_model(self, model_id: int):
        """Remove a model from a mapping alias."""
        if self.mapping_model_repo is None:
            return False
        return self.mapping_model_repo.remove_model(model_id)

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
