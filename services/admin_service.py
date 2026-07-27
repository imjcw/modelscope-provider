"""Admin service for the management panel."""
import datetime
import uuid

from core.timezone import TZ, today, today_range, now as _tz_now

from repositories.account_repository import AccountRepository
from repositories.client_api_key_repository import ClientApiKeyRepository
from repositories.config_repository import ConfigRepository
from repositories.log_repository import LogRepository
from repositories.mapping_repository import MappingRepository
from repositories.mapping_model_repository import MappingModelRepository
from repositories.provider_type_repository import ProviderTypeRepository
from repositories.quota_repository import QuotaRepository
from repositories.supplier_model_repository import SupplierModelRepository
from services.providers import build_rate_limit_strategies, create_strategy


class AdminService:
    """High-level admin operations."""

    def __init__(self, account_repo: AccountRepository,
                 mapping_repo: MappingRepository,
                 config_repo: ConfigRepository,
                 log_repo: LogRepository,
                 quota_repo: QuotaRepository = None,
                 supplier_model_repo: SupplierModelRepository = None,
                 mapping_model_repo: MappingModelRepository = None,
                 client_key_repo: ClientApiKeyRepository = None,
                 provider_type_repo: ProviderTypeRepository = None,
                 rate_limit_strategies: dict = None,
                 db=None,
                 quota_updater=None,
                 config_cache=None,
                 rate_limit_cache=None):
        self.account_repo = account_repo
        self.mapping_repo = mapping_repo
        self.config_repo = config_repo
        self.log_repo = log_repo
        self.quota_repo = quota_repo
        self.rate_limit_strategies = rate_limit_strategies or {}
        self.supplier_model_repo = supplier_model_repo
        self.mapping_model_repo = mapping_model_repo
        self.client_key_repo = client_key_repo
        self.provider_type_repo = provider_type_repo
        self.db = db
        self.quota_updater = quota_updater
        self.config_cache = config_cache
        self.rate_limit_cache = rate_limit_cache

    # ── Accounts ──

    def get_suppliers(self):
        """List suppliers enriched with today's quota info (when quota_repo set)."""
        suppliers = self.account_repo.find_all()
        for s in suppliers:
            self._enrich_quota(s)
        return suppliers

    def get_supplier(self, supplier_id: int):
        s = self.account_repo.find_by_id(supplier_id)
        if s:
            self._enrich_quota(s)
        return s

    def _enrich_quota(self, supplier: dict):
        """Enrich a supplier dict with quota info from the appropriate strategy."""
        provider_type = supplier.get("provider_type", "modelscope")
        strategy = self.rate_limit_strategies.get(provider_type)

        if strategy:
            info = strategy.get_quota_info(supplier["account_id"])
            supplier["quota_remaining"] = info.get("quota_remaining", 0)
            supplier["quota_limit"] = info.get("quota_limit", 0)
        elif self.quota_repo is not None:
            info = self.quota_repo.get_account_info(supplier["account_id"])
            if info:
                supplier["quota_remaining"] = info["quota_remaining"]
                supplier["quota_limit"] = info["quota_limit"]
            else:
                supplier["quota_remaining"] = 0
                supplier["quota_limit"] = 0
        else:
            supplier.setdefault("quota_remaining", 0)
            supplier.setdefault("quota_limit", 0)

    def create_supplier(self, name: str, api_key: str,
                        base_url: str, provider_type: str = "modelscope") -> dict:
        return self.account_repo.create(name, api_key, base_url,
                                        provider_type=provider_type)

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

    # ── Provider Types ──

    def get_provider_types(self):
        """List all provider types (config parsed to dict)."""
        if self.provider_type_repo is None:
            return []
        return self.provider_type_repo.find_all()

    def create_provider_type(self, type_key: str, name: str, description: str = "",
                             strategy_type: str = "header_based",
                             config: dict = None, color: str = "#89b4fa") -> dict:
        if self.provider_type_repo is None:
            raise NotImplementedError("Provider type repo not configured")
        created = self.provider_type_repo.create(
            type_key=type_key, name=name, description=description,
            strategy_type=strategy_type, config=config or {}, color=color,
        )
        self.rebuild_rate_limit_strategies()
        return created

    def update_provider_type(self, type_id: int, **kwargs) -> dict:
        if self.provider_type_repo is None:
            raise NotImplementedError("Provider type repo not configured")
        updated = self.provider_type_repo.update(type_id, **kwargs)
        if updated:
            self.rebuild_rate_limit_strategies()
        return updated

    def delete_provider_type(self, type_id: int) -> bool:
        if self.provider_type_repo is None:
            return False
        pt = self.provider_type_repo.find_by_id(type_id)
        if not pt:
            return False
        if pt.get("built_in"):
            raise ValueError("内置供应商类型不可删除")
        if self.provider_type_repo.count_accounts_by_type(pt["type_key"]) > 0:
            raise ValueError("该类型下仍有供应商，无法删除")
        ok = self.provider_type_repo.delete(type_id)
        if ok:
            self.rebuild_rate_limit_strategies()
        return ok

    def rebuild_rate_limit_strategies(self) -> None:
        """按最新供应商类型表原地重建策略字典。

        原地清空再填充，使 services 中共享的同一 dict 引用同步更新，
        路由层无需重启即可使用新策略配置。先确保硬编码的内置类型始终可用。
        """
        fallback = {
            "modelscope": create_strategy(
                "header_based",
                quota_updater=self.quota_updater,
                quota_repository=self.quota_repo,
            ),
            "sensetime": create_strategy(
                "fixed_window", db=self.db,
            ),
        }
        self.rate_limit_strategies.clear()
        self.rate_limit_strategies.update(fallback)

        if self.provider_type_repo is not None:
            try:
                db_types = self.provider_type_repo.find_all()
                if db_types:
                    db_strategies = build_rate_limit_strategies(
                        db_types, self.db, self.quota_updater, self.quota_repo,
                    )
                    self.rate_limit_strategies.update(db_strategies)
            except Exception:
                pass

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
        """Replace a supplier's model catalog.

        FK CASCADE on mapping_models.supplier_model_id ensures that
        bindings pointing to removed models are automatically cleaned up.
        """
        if self.supplier_model_repo is None:
            return []
        self.supplier_model_repo.bulk_upsert(supplier_id, models)
        return self.supplier_model_repo.find_by_supplier(supplier_id)

    # ── Supplier Import / Export ──

    def export_suppliers(self) -> dict:
        """Export all suppliers with their models as a structured dict.

        The returned dict is JSON/YAML-serializable and includes metadata
        (version, exported_at) plus the full supplier list including models.
        """
        suppliers = self.account_repo.find_all()
        result = []
        for sup in suppliers:
            models = []
            if self.supplier_model_repo is not None:
                models = self.supplier_model_repo.find_by_supplier(sup["id"])
            result.append({
                "name": sup.get("name", ""),
                "api_key": sup.get("api_key", ""),
                "base_url": sup.get("base_url", ""),
                "provider_type": sup.get("provider_type", "modelscope"),
                "status": sup.get("status", "active"),
                "models": [
                    {
                        "model_name": m.get("model_name", ""),
                        "model_type": m.get("model_type", "text"),
                        "context_length": m.get("context_length"),
                    }
                    for m in models
                ],
            })
        return {
            "version": "1.0",
            "exported_at": _tz_now().isoformat(timespec="seconds"),
            "suppliers": result,
        }

    def import_suppliers(self, data: dict, strategy: str = "skip") -> dict:
        """Import suppliers from a previously exported data structure.

        Args:
            data: Parsed dict from JSON/YAML import.
            strategy: How to handle duplicate names — "skip" (default) or "overwrite".

        Returns:
            Stats dict: {created, skipped, updated, errors, total}
        """
        if not isinstance(data, dict) or "suppliers" not in data:
            raise ValueError("无效的导入格式：缺少 'suppliers' 字段")

        entries = data["suppliers"]
        if not isinstance(entries, list):
            raise ValueError("无效的导入格式：'suppliers' 必须是列表")

        stats = {"created": 0, "skipped": 0, "updated": 0, "errors": [], "total": len(entries)}

        for idx, entry in enumerate(entries):
            try:
                # ── Validate required fields ──
                name = entry.get("name", "").strip()
                api_key = entry.get("api_key", "").strip()
                base_url = entry.get("base_url", "").strip()
                if not name or not api_key or not base_url:
                    raise ValueError("缺少必填字段 name / api_key / base_url")

                status = entry.get("status", "active")
                provider_type = entry.get("provider_type", "modelscope")
                models = entry.get("models", [])

                # ── Check for duplicate by name ──
                existing = self.account_repo.find_by_name(name)
                if existing:
                    if strategy == "skip":
                        stats["skipped"] += 1
                        continue
                    elif strategy == "overwrite":
                        self.account_repo.update(
                            existing["id"],
                            api_key=api_key,
                            base_url=base_url,
                            status=status,
                            provider_type=provider_type,
                        )
                        if self.supplier_model_repo is not None and isinstance(models, list):
                            self._safe_bulk_models(existing["id"], models)
                        stats["updated"] += 1
                        continue
                    else:
                        raise ValueError(f"未知的处理策略: {strategy}")

                # ── Create new supplier ──
                created = self.account_repo.create(
                    name=name, api_key=api_key, base_url=base_url,
                    status=status, provider_type=provider_type,
                )
                if self.supplier_model_repo is not None and isinstance(models, list):
                    self._safe_bulk_models(created["id"], models)
                stats["created"] += 1

            except Exception as e:
                stats["errors"].append(f"第 {idx + 1} 项 ({entry.get('name', '?')}): {str(e)}")

        return stats

    def _safe_bulk_models(self, supplier_id: int, models: list) -> None:
        """Bulk-insert models for a supplier, skipping invalid entries."""
        cleaned = []
        for m in models:
            if not isinstance(m, dict):
                continue
            mn = m.get("model_name", "").strip()
            if not mn:
                continue
            cleaned.append({
                "model_name": mn,
                "model_type": m.get("model_type", "text"),
                "context_length": m.get("context_length"),
            })
        if cleaned:
            self.supplier_model_repo.bulk_upsert(supplier_id, cleaned)

    # ── Mappings ──

    def get_mappings(self):
        return self.mapping_repo.find_all()

    def get_mappings_by_alias(self, alias_name: str):
        return self.mapping_repo.find_by_alias(alias_name)

    def upsert_mapping(self, alias_name: str, actual_model_id: str,
                       description: str = "", status: str = "active"):
        return self.mapping_repo.create(alias_name, actual_model_id, description, status)

    def update_mapping(self, alias_name: str, **kwargs):
        """Update mapping fields. Supported: actual_model_id, description, status."""
        return self.mapping_repo.update(alias_name, **kwargs)

    def toggle_mapping_status(self, alias_name: str):
        """Toggle mapping status between 'active' and 'disabled'."""
        return self.mapping_repo.toggle_status(alias_name)

    def bulk_update_mappings(self, mappings: dict):
        self.mapping_repo.bulk_upsert(mappings)

    def delete_mapping(self, alias_name: str):
        return self.mapping_repo.delete_by_alias(alias_name)

    def get_mapping_models(self, alias_name: str):
        """Get all models bound to a mapping alias (with model_type, context_length)."""
        if self.mapping_model_repo is None:
            return []
        return self.mapping_model_repo.find_by_alias(alias_name)

    def add_mapping_model(
        self, alias_name: str, supplier_model_id: int, sort_order: int = 0
    ) -> dict:
        """Add a model to a mapping alias.

        Validates that the supplier_model_id points to an existing row.
        The FK on mapping_models.supplier_model_id guarantees consistency,
        but we validate early for a clear error message.
        """
        if self.mapping_model_repo is None:
            raise NotImplementedError("Mapping model repo not configured")
        # Validate: the supplier_model_id must exist
        if self.supplier_model_repo is not None:
            if self.supplier_model_repo.find_by_id(supplier_model_id) is None:
                raise ValueError(
                    f"supplier_model_id {supplier_model_id} 不存在，无法绑定"
                )
        return self.mapping_model_repo.add_model(
            alias_name, supplier_model_id=supplier_model_id, sort_order=sort_order
        )

    def reorder_mapping_models(self, alias_name: str, ordered_ids: list):
        """Reorder binding list for an alias.

        Args:
            alias_name: virtual model ID.
            ordered_ids: list of mapping_models ids in desired order.
        """
        if self.mapping_model_repo is None:
            raise NotImplementedError("Mapping model repo not configured")
        return self.mapping_model_repo.reorder(alias_name, ordered_ids)

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
        # Sync memory cache so hot path reads are fresh
        if self.config_cache is not None:
            for key, value in config.items():
                self.config_cache.set(key, str(value))

    def cleanup_old_logs(self):
        """Delete log entries older than the configured retention period.

        Reads ``log_retention_hours`` from system_config (default 1 hour).
        Runs inline — designed to be called periodically from a background task.
        """
        import datetime

        raw = self.config_repo.get("log_retention_hours") or "1"
        try:
            hours = float(raw)
        except (ValueError, TypeError):
            hours = 1.0
        # Guard against non-positive values that would wipe all logs
        if hours <= 0:
            hours = 1.0

        cutoff = (
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(hours=hours)
        ).strftime("%Y-%m-%d %H:%M:%S")

        deleted = self.log_repo.delete_older_than(cutoff)
        if deleted > 0:
            logger.info(
                "Cleaned up %d log entries older than %s (retention=%sh)",
                deleted, cutoff, raw,
            )

    # ── Mapping usage ────────────────────────────────────────────────────

    def get_mapping_usage(self, alias_name: str, days: int = 7):
        """Aggregated usage stats for one virtual model over the last ``days``.

        Reads from the pre-aggregated ``request_stats_minute`` table, so it
        is not affected by ``request_logs`` retention.

        Returns:
          { alias, period_days,
            usage: { requests, input_tokens, output_tokens, cache_tokens,
                     error_count, cache_hit_rate,
                     per_model: [{ supplier, model, display,
                                   requests, input_tokens, output_tokens,
                                   cache_tokens, error_count }, ...] } }
        """
        from datetime import timedelta

        cutoff = (_tz_now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

        bound = self.mapping_model_repo.find_by_alias(alias_name) if self.mapping_model_repo else []

        # (supplier_id → supplier_name) lookup — keyed by supplier_id (unique per binding),
        # not model_name (which can be identical across different suppliers).
        # A supplier account has two identifiers: the integer row ``id`` (== supplier_id
        # in the binding) and the UUID ``account_id``. Depending on the request path the
        # stats table may store either, so we match on both when attributing usage.
        sup_name_by_id = {}
        sid_to_keys = {}  # supplier_id -> set of identifier strings to match stats rows
        for b in bound:
            sid = b.get("supplier_id")
            if sid is None:
                continue
            acc = self.account_repo.find_by_id(sid)
            sup_name_by_id[sid] = acc.get("name", "") if acc else ""
            keys = {str(sid)}
            if acc and acc.get("account_id") is not None:
                keys.add(str(acc["account_id"]))
            sid_to_keys[sid] = keys

        # Query stats by virtual_model — each row is grouped by (model, account_id).
        stats_rows = self.log_repo.query_stats_by_virtual_model(cutoff, alias_name)
        # Group stats rows by model name; the account_id of each row may be either the
        # integer id or the UUID account_id, so we test membership against sid_to_keys.
        stats_by_model = {}
        for r in stats_rows:
            stats_by_model.setdefault(r["model"], []).append(r)

        totals = dict(requests=0, input_tokens=0, output_tokens=0,
                      cache_tokens=0, error_count=0)

        per_model_rows: list[dict] = []
        seen_keys = set()  # deduplicate by (model name, supplier id)
        for b in bound:
            mn = b["model_name"]
            sid = b.get("supplier_id")
            key = (mn, str(sid))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            # Attribute to the supplier's own stats row only (same model name bound to a
            # different supplier must not be merged into this row).
            s = {}
            match_keys = sid_to_keys.get(sid, {str(sid)})
            for row in stats_by_model.get(mn, []):
                if str(row["account_id"]) in match_keys:
                    s = row
                    break
            req = s.get("requests", 0) or 0
            inp = s.get("input_tokens", 0) or 0
            out = s.get("output_tokens", 0) or 0
            cache = s.get("cached_tokens", 0) or 0
            err = req - (s.get("success", 0) or 0)
            totals["requests"] += req
            totals["input_tokens"] += inp
            totals["output_tokens"] += out
            totals["cache_tokens"] += cache
            totals["error_count"] += err
            per_model_rows.append(dict(
                supplier=sup_name_by_id.get(sid, ""),
                supplier_id=sid,
                model=mn,
                display=b.get("display_name", mn),
                requests=req,
                input_tokens=inp,
                output_tokens=out,
                cache_tokens=cache,
                error_count=err,
            ))

        cache_hit_rate = round(
            totals["cache_tokens"] / (totals["cache_tokens"] + totals["input_tokens"]) * 100, 1
        ) if (totals["cache_tokens"] + totals["input_tokens"]) > 0 else 0.0

        return {
            "alias": alias_name,
            "period_days": days,
            "usage": {
                "requests": totals["requests"],
                "input_tokens": totals["input_tokens"],
                "output_tokens": totals["output_tokens"],
                "cache_tokens": totals["cache_tokens"],
                "error_count": totals["error_count"],
                "cache_hit_rate": cache_hit_rate,
                "per_model": per_model_rows,
            },
        }

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
                    raw_response: str = None,
                    request_start: str = None, first_response: str = None, end_time: str = None,
                    cached_tokens: int = 0, prompt_partial_cached: int = 0,
                    client_key_name: str = None,
                    response_headers: str = None) -> str:
        """Log a request and return its request_id."""
        request_id = f"req_{uuid.uuid4().hex[:8]}"

        # Compute latency_ms from timing fields if not provided
        if latency_ms is None and request_start and end_time:
            try:
                from datetime import datetime, timezone

                def parse_ts(ts: str) -> float:
                    # Normalise space→T separator; strip trailing Z
                    ts = ts.replace(" ", "T").rstrip("Z")
                    dt = datetime.fromisoformat(ts)
                    # If naive (no tz info), treat as UTC — matches what routes.py stores
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt.timestamp()

                latency_ms = int((parse_ts(end_time) - parse_ts(request_start)) * 1000)
            except Exception:
                latency_ms = None

        self.log_repo.create(
            request_id=request_id, model=model, actual_model_id=actual_model_id,
            account_id=account_id, account_name=account_name, status_code=status_code,
            input_tokens=input_tokens, output_tokens=output_tokens,
            latency_ms=latency_ms, is_stream=is_stream,
            error_message=error_message, raw_request=raw_request,
            raw_response=raw_response,
            request_start=request_start, first_response=first_response, end_time=end_time,
            cached_tokens=cached_tokens, prompt_partial_cached=prompt_partial_cached,
            client_key_name=client_key_name,
            response_headers=response_headers,
            )

        # Update minute-level aggregated stats (independent of raw log retention)
        try:
            # Use request_start if available, otherwise fall back to end_time
            ts = request_start or end_time or _tz_now().isoformat()
            # Normalise space→T separator; strip trailing Z
            ts = ts.replace(" ", "T").rstrip("Z")
            self.log_repo.upsert_stats(
                timestamp=ts,
                model=actual_model_id or model,
                virtual_model=model if actual_model_id else "",
                account_id=account_id or "",
                client_key_name=client_key_name or "",
                status_code=status_code,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                latency_ms=latency_ms,
                cached_tokens=cached_tokens + prompt_partial_cached,
            )
        except Exception:
            logger.warning("Failed to update request stats", exc_info=True)

        return request_id

    # ── Client API Keys ──

    def get_client_keys(self):
        """List all client API keys enriched with today's usage stats.

        Reads from the pre-aggregated ``request_stats_minute`` table, so it
        survives ``request_logs`` retention cleanup.
        """
        if self.client_key_repo is None:
            return []
        keys = self.client_key_repo.find_all()
        today_start = today()
        for k in keys:
            k["today_requests"] = 0
            k["today_input_tokens"] = 0
            k["today_output_tokens"] = 0
            k["today_cache_tokens"] = 0
            try:
                s = self.log_repo.query_stats_client_key(today_start, k["name"])
                k["today_requests"] = s.get("requests", 0) or 0
                k["today_input_tokens"] = s.get("input_tokens", 0) or 0
                k["today_output_tokens"] = s.get("output_tokens", 0) or 0
                k["today_cache_tokens"] = s.get("cached_tokens", 0) or 0
            except Exception:
                pass
        return keys

    def create_client_key(self, name: str, description: str = "") -> dict:
        """Create a new client API key."""
        if self.client_key_repo is None:
            raise NotImplementedError("Client key repo not configured")
        return self.client_key_repo.create(name, description)

    def update_client_key(
        self, key_id: int, name: str = None, description: str = None,
        status: str = None
    ) -> dict:
        """Update client API key fields."""
        if self.client_key_repo is None:
            raise NotImplementedError("Client key repo not configured")
        kwargs = {}
        if name is not None:
            kwargs["name"] = name
        if description is not None:
            kwargs["description"] = description
        if status is not None:
            kwargs["status"] = status
        return self.client_key_repo.update(key_id, **kwargs) if kwargs else None

    def delete_client_key(self, key_id: int) -> bool:
        """Delete a client API key."""
        if self.client_key_repo is None:
            return False
        return self.client_key_repo.delete(key_id)

    def get_key_usage(
        self, key_id: int, page: int = 0, page_size: int = 50, **filters
    ):
        """Get usage logs for a specific client API key."""
        if self.client_key_repo is None:
            return [], 0
        key = self.client_key_repo.find_by_id(key_id)
        if not key:
            return [], 0
        records, total = self.log_repo.find_all(
            page=page,
            page_size=page_size,
            client_key_name=key["name"],
            **filters,
        )
        return records, total

    def get_key_stats(self, key_id: int, days: int = 30):
        """Get aggregate statistics for a specific client API key.

        Reads from the pre-aggregated ``request_stats_minute`` table, so it
        survives ``request_logs`` retention cleanup.

        Note on avg_latency_ms: the stats table only stores ``latency_sum`` and
        ``latency_count`` (non-None latencies only).  So the average is computed
        over requests that actually reported a latency, which differs from the
        legacy behaviour that treated missing latency values as 0.
        """
        if self.client_key_repo is None:
            return {}
        key = self.client_key_repo.find_by_id(key_id)
        if not key:
            return {}
        from datetime import timedelta

        cutoff = (_tz_now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")

        total = self.log_repo.query_stats_key_summary(cutoff, key["name"])
        total_requests = total.get("total", 0) or 0
        success_count = total.get("success", 0) or 0
        total_input = total.get("input_tokens", 0) or 0
        total_output = total.get("output_tokens", 0) or 0
        total_cache = total.get("cached_tokens", 0) or 0
        error_count = total_requests - success_count
        latency_sum = total.get("latency_sum", 0) or 0
        latency_count = total.get("latency_count", 0) or 0
        avg_latency = (
            round(latency_sum / latency_count)
            if latency_count > 0
            else 0
        )

        # Per-model breakdown
        per_model_list = []
        for row in self.log_repo.query_stats_key_per_model(cutoff, key["name"]):
            m_req = row.get("requests", 0) or 0
            m_success = row.get("success", 0) or 0
            per_model_list.append(dict(
                model=row.get("model", "unknown"),
                requests=m_req,
                input_tokens=row.get("input_tokens", 0) or 0,
                output_tokens=row.get("output_tokens", 0) or 0,
                cache_tokens=row.get("cached_tokens", 0) or 0,
                error_count=m_req - m_success,
            ))

        return {
            "key_name": key["name"],
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_tokens": total_cache,
            "success_count": success_count,
            "error_count": error_count,
            "avg_latency_ms": avg_latency,
            "per_model": per_model_list,
        }

    def get_key_docs(self, key_id: int, base_url: str = None):
        """Return integration meta-data for a client API key.

        Only dynamic data is returned — the rendering is done in the frontend
        to keep documentation content, code snippets, and error-table content
        in a single source of truth (Guide.vue).

        Args:
            key_id: Client API key primary key.
            base_url: Real service base URL (e.g. ``https://example.com/api/v1``).
        """
        if self.client_key_repo is None:
            return {}
        key = self.client_key_repo.find_by_id(key_id)
        if not key:
            return {}
        if not base_url:
            base_url = "https://your-domain.com/api/v1"
        return {"key_value": key["key_value"], "base_url": base_url}

    # ── Model Quotas ──

    def get_model_quotas(self):
        """Get model-level quota info by supplier + model.

        Reads from model_quotas table (populated from modelscope-ratelimit-model-requests-* headers).
        Falls back to request_logs for token usage if no model quota entry exists.

        Returns a list of dicts:
        - supplier_id, supplier_name, account_id
        - model_name, model_type
        - quota_remaining, quota_limit (from model_quotas table)
        - today_input_tokens, today_output_tokens (from model_quotas or request_logs)
        - is_unavailable
        """
        if self.quota_repo is None or self.supplier_model_repo is None:
            return []

        # Get all suppliers
        suppliers = self.account_repo.find_all()

        # Get supplier-level quota info for unavailable_models
        supplier_quota_map = {}
        for sup in suppliers:
            aid = sup["account_id"]
            info = self.quota_repo.get_account_info(aid) if self.quota_repo else None
            unavailable = set()
            if info and "unavailable_models" in info:
                um = info["unavailable_models"]
                if isinstance(um, set):
                    unavailable = um
                elif isinstance(um, list):
                    unavailable = set(um)
            supplier_quota_map[aid] = {
                "quota_remaining": info["quota_remaining"] if info else 0,
                "quota_limit": info["quota_limit"] if info else 0,
                "unavailable_models": unavailable,
            }

        result = []
        for sup in suppliers:
            sid = sup["id"]
            account_id = sup["account_id"]
            sup_name = sup.get("name", "")

            # Get model-level quotas for this supplier
            model_quotas = self.quota_repo.get_model_quotas(account_id)
            model_quota_map = {m["model_name"]: m for m in model_quotas}

            # Get all models for this supplier
            models = self.supplier_model_repo.find_by_supplier(sid)

            for m in models:
                model_name = m.get("model_name", "")
                model_type = m.get("model_type", "text")

                # Get model-level quota from model_quotas table
                mq = model_quota_map.get(model_name, {})
                quota_remaining = mq.get("quota_remaining", 0)
                quota_limit = mq.get("quota_limit", 0)
                today_input = mq.get("total_input_tokens", 0) or 0
                today_output = mq.get("total_output_tokens", 0) or 0

                # Fallback: if no model quota entry yet, derive from request_logs
                if quota_limit == 0 and today_input == 0 and today_output == 0:
                    today_input, today_output = self._get_today_token_usage(account_id, model_name)

                is_unavailable = model_name in supplier_quota_map.get(account_id, {}).get("unavailable_models", set())

                result.append({
                    "supplier_id": sid,
                    "supplier_name": sup_name,
                    "account_id": account_id,
                    "model_name": model_name,
                    "model_type": model_type,
                    "quota_remaining": quota_remaining,
                    "quota_limit": quota_limit,
                    "today_input_tokens": today_input,
                    "today_output_tokens": today_output,
                    "is_unavailable": is_unavailable,
                })

        return result

    def _get_today_token_usage(self, account_id: str, model_name: str) -> tuple:
        """Get today's input and output token totals for an account+model from
        the pre-aggregated ``request_stats_minute`` table.
        """
        start_of_day, end_of_day = today_range()
        return self.log_repo.query_stats_today_token_usage(
            account_id, model_name, start_of_day, end_of_day,
        )

    # ── Stats ──

    def get_stats(self, days: int = 30):
        """Aggregate statistics for the given period.

        Reads from the pre-aggregated ``request_stats_minute`` table, so it
        survives ``request_logs`` retention cleanup.
        """
        from datetime import timedelta

        cutoff = (_tz_now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        now = _tz_now().strftime("%Y-%m-%d %H:%M:%S")

        global_totals = self.log_repo.query_stats_global(cutoff, now)
        total_requests = global_totals.get("total", 0) or 0
        total_input = global_totals.get("input_tokens", 0) or 0
        total_output = global_totals.get("output_tokens", 0) or 0
        total_cached = global_totals.get("cached_tokens", 0) or 0

        # Top models by token usage
        model_rows = self.log_repo.query_stats_model_usage(cutoff, now)
        grand_total = sum(r["tokens"] or 0 for r in model_rows)
        top_models = []
        for r in model_rows[:5]:
            tok = r["tokens"] or 0
            top_models.append({
                "model": r["model"],
                "tokens": tok,
                "pct": round(tok / grand_total * 100, 1) if grand_total > 0 else 0,
            })

        # Daily trend: {date: {input, output, cached, total}}
        daily_trend = {}
        for r in self.log_repo.query_stats_daily_trend(cutoff, now):
            date_str = r["date"]
            inp = r["input_tokens"] or 0
            out = r["output_tokens"] or 0
            cached = r["cached_tokens"] or 0
            daily_trend[date_str] = {
                "input": inp,
                "output": out,
                "cached": cached,
                "total": inp + out,
            }

        # Model usage dict (full, not just top 5)
        model_usage = {r["model"]: r["tokens"] or 0 for r in model_rows}

        # Heatmap: { "weekday,hour": count }
        heatmap = {}
        for r in self.log_repo.query_stats_heatmap(cutoff, now):
            heatmap[f'{r["weekday"]},{r["hour"]}'] = r["count"] or 0

        # Supplier daily: {account_id: {date: tokens}}
        supplier_daily: dict = {}
        for r in self.log_repo.query_stats_supplier_daily(cutoff, now):
            supplier_daily.setdefault(r["account_id"], {}).setdefault(r["date"], 0)
            supplier_daily[r["account_id"]][r["date"]] += r["tokens"] or 0

        # Daily model breakdown: {date: {model: tokens}} — same shape as
        # the legacy request_logs path, read from the stats table.
        daily_tokens = {}
        for r in self.log_repo.query_stats_daily_model_usage(cutoff, now):
            date_str = r["date"]
            daily_tokens.setdefault(date_str, {})[r["model"]] = r["tokens"] or 0

        # Cache hit rate: cached / (cached + input)
        denom = total_cached + total_input
        cache_hit_rate = round(total_cached / denom * 100, 1) if denom > 0 else 0.0

        return {
            "heatmap": heatmap,
            "daily_tokens": daily_tokens,
            "model_usage": model_usage,
            "total_requests": total_requests,
            # Dashboard fields
            "total_tokens": total_input + total_output,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "cached_tokens_total": total_cached,
            # prompt_partial_cached is folded into cached_tokens in the stats
            # table (upsert_stats adds cached_tokens + prompt_partial_cached
            # together), so this field is 0 by design.
            "partial_cached_total": 0,
            "cache_hit_rate": cache_hit_rate,
            "daily_trend": daily_trend,
            "top_models": top_models,
            "supplier_daily": supplier_daily,
        }

    # Window (seconds) → bucket granularity for the dashboard presets;
    # other windows get ~30 buckets.
    _WINDOW_BUCKET_MAP = {86400: 3600, 604800: 86400, 2592000: 86400}

    def get_window_stats(self, seconds: int = 300) -> dict:
        """Windowed statistics for the dashboard live panel.

        Aggregates [now - seconds, now] in SQL: KPIs (total / success rate /
        QPS / avg latency) with previous-window deltas, a bucketed series for
        the trend chart, status-code breakdown and per-model call counts.

        Series buckets are epoch-aligned (bucket_start divisible by
        bucket_seconds) and span the bucket containing `start` through the one
        containing `end` inclusive, so len(series) is seconds // bucket or
        seconds // bucket + 1. The trailing bucket is usually still in
        progress; its qps is computed over its elapsed portion only.
        """
        import calendar
        import time
        from datetime import datetime, timedelta, timezone

        seconds = max(60, min(int(seconds or 300), 2592000))
        bucket = self._WINDOW_BUCKET_MAP.get(seconds, max(1, seconds // 30))

        fmt = "%Y-%m-%d %H:%M:%S"
        now = datetime.now(TZ)
        start_dt = now - timedelta(seconds=seconds)
        start, end = start_dt.strftime(fmt), now.strftime(fmt)

        # Current window vs previous window (exclusive right bound: no overlap)
        cur = self.log_repo.query_stats_summarize(start, end)
        prev = self.log_repo.query_stats_summarize(
            (start_dt - timedelta(seconds=seconds)).strftime(fmt), start
        )

        total = cur["total"] or 0
        success = cur["success"] or 0
        total_tokens = cur["total_tokens"] or 0
        input_tokens = cur["input_tokens"] or 0
        output_tokens = cur["output_tokens"] or 0
        cached_tokens = cur["cached_tokens"] or 0
        avg_latency = cur["avg_latency_ms"]
        success_rate = round(success / total * 100, 1) if total else None
        cache_hit_rate = round(cached_tokens / input_tokens * 100, 1) if input_tokens else 0.0

        prev_total = prev["total"] or 0
        prev_tokens = prev["total_tokens"] or 0
        prev_cached = prev["cached_tokens"] or 0
        prev_input = prev["input_tokens"] or 0
        prev_rate = round((prev["success"] or 0) / prev_total * 100, 1) if prev_total else None
        prev_avg = prev["avg_latency_ms"]
        prev_hit_rate = round(prev_cached / prev_input * 100, 1) if prev_input else 0.0

        def pct_delta(cur_v, prev_v):
            if cur_v is None or not prev_v:
                return None
            return round((cur_v - prev_v) / prev_v * 100, 1)

        delta = {
            "total_pct": pct_delta(total, prev_total),
            "total_tokens_pct": pct_delta(total_tokens, prev_tokens),
            "success_rate_pp": (
                round(success_rate - prev_rate, 1)
                if success_rate is not None and prev_rate is not None else None
            ),
            "avg_latency_pct": pct_delta(avg_latency, prev_avg),
            "cached_tokens_pct": pct_delta(cached_tokens, prev_cached),
            "cache_hit_rate_pp": (
                round(cache_hit_rate - prev_hit_rate, 1)
                if prev_input else None
            ),
        }

        # Bucketed series: SQL returns only non-empty epoch-aligned buckets;
        # fill the full grid so the chart always renders a continuous axis.
        # 日级（>=86400s）桶按上海本地日历对齐到当天 00:00，与 repos 内
        # strftime('%Y-%m-%d 00:00:00', bucket) 的截断保持一致；子级桶用 epoch 整除即可
        # （粒度均整除 8h，上海界与 UTC 界重合）。
        start_epoch = int(start_dt.timestamp())
        end_epoch = int(now.timestamp())
        if bucket >= 86400:
            first_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0)
            first_epoch = int(first_dt.timestamp())
            n_buckets = (end_epoch - first_epoch) // bucket + 1
        else:
            first_epoch = (start_epoch // bucket) * bucket
            n_buckets = (end_epoch // bucket - start_epoch // bucket) + 1

        series = []
        for i in range(n_buckets):
            b_epoch = first_epoch + i * bucket
            series.append({
                "t": datetime.fromtimestamp(b_epoch, tz=TZ).strftime(fmt),
                "_epoch": b_epoch,
                "total": 0,
                "success": 0,
                "total_tokens": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "avg_latency_ms": None,
            })
        by_epoch = {cell["_epoch"]: cell for cell in series}
        for row in self.log_repo.query_stats_aggregate(start, end, bucket):
            cell = by_epoch.get(
                int(datetime.strptime(row["bucket_start"], fmt).replace(tzinfo=TZ).timestamp())
            )
            if cell is not None:
                cell["total"] = row["total"] or 0
                cell["success"] = row["success"] or 0
                cell["total_tokens"] = row["total_tokens"] or 0
                cell["input_tokens"] = row["input_tokens"] or 0
                cell["output_tokens"] = row["output_tokens"] or 0
                cell["cached_tokens"] = row["cached_tokens"] or 0
                cell["avg_latency_ms"] = row["avg_latency_ms"]

        for cell in series:
            b_total, b_success = cell.pop("total"), cell.pop("success")
            b_epoch = cell.pop("_epoch")
            # Trailing bucket may be partial: rate over the elapsed portion.
            elapsed = max(1, min(bucket, end_epoch - b_epoch))
            cell["total"] = b_total
            cell["success"] = b_success
            cell["qps"] = round(b_total / elapsed, 1)
            cell["success_rate"] = round(b_success / b_total * 100, 1) if b_total else None

        # Status-code breakdown: still reads from request_logs (only recent data).
        # For older periods, status codes are not available in the stats table.
        status_codes = {}
        for row in self.log_repo.query_stats_status_breakdown(start, end):
            if row["status_code"] is not None:
                status_codes[str(row["status_code"])] = row["count"]

        # Per-model call counts from aggregated stats table. Grouped by
        # (model, account_id) so the same model name on different suppliers is
        # kept separate and aligns with the quota rows by account_id.
        models = []
        for row in self.log_repo.query_stats_per_model(start, end):
            m_total = row["total"] or 0
            m_success = row["success"] or 0
            m_input = row["input_tokens"] or 0
            m_output = row["output_tokens"] or 0
            m_cached = row["cached_tokens"] or 0
            models.append({
                "model": row["model"],
                "account_id": row.get("account_id"),
                "total": m_total,
                "success": m_success,
                "success_rate": round(m_success / m_total * 100, 1) if m_total else None,
                "total_tokens": m_input + m_output,
                "input_tokens": m_input,
                "output_tokens": m_output,
                "cached_tokens": m_cached,
                "cache_hit_rate": round(m_cached / m_input * 100, 1) if m_input else 0.0,
            })

        return {
            "window_seconds": seconds,
            "bucket_seconds": bucket,
            "start": start,
            "end": end,
            "kpi": {
                "total": total,
                "success": success,
                "failed": total - success,
                "total_tokens": total_tokens,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cached_tokens": cached_tokens,
                "success_rate": success_rate,
                "cache_hit_rate": cache_hit_rate,
                "qps": round(total / seconds, 1),
                "avg_latency_ms": round(avg_latency) if avg_latency is not None else None,
                "delta": delta,
            },
            "prev": {
                "total": prev_total,
                "total_tokens": prev_tokens,
                "success_rate": prev_rate,
                "qps": round(prev_total / seconds, 1),
                "avg_latency_ms": round(prev_avg) if prev_avg is not None else None,
            },
            "series": series,
            "status_codes": status_codes,
            "models": models,
        }
