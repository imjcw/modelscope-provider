"""Admin service for the management panel."""
import datetime
from datetime import timezone as _UTC_TZ
_UTC = _UTC_TZ.utc
import logging
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
from services.models_cache import invalidate as invalidate_models_cache
from services.usage import normalize_cache_usage
from models.account import DEFAULT_ANTHROPIC_STREAM_PROTOCOL, DEFAULT_PROVIDER_TYPE

logger = logging.getLogger(__name__)


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
        """List suppliers enriched with today's quota info and API keys."""
        suppliers = self.account_repo.find_all()
        if not suppliers:
            return []
        # Batch-load API keys for all suppliers in one query instead of one
        # query per supplier (P2 / N+1).
        key_map: dict = {}
        if self.account_repo is not None:
            try:
                key_map = self.account_repo.find_api_keys_by_account_ids(
                    [s["id"] for s in suppliers]
                ) or {}
            except Exception:
                logger.warning("Failed to batch-load API keys for suppliers",
                               exc_info=True)
        for s in suppliers:
            self._enrich_quota(s)
            self._enrich_api_keys(s, key_map.get(s["id"]))
        return suppliers

    def get_supplier(self, supplier_id: int):
        s = self.account_repo.find_by_id(supplier_id)
        if s:
            self._enrich_quota(s)
            self._enrich_api_keys(s)
        return s

    def _enrich_api_keys(self, supplier: dict, records: list = None) -> None:
        """Add api_keys list and api_key_records to supplier dict from account_api_keys table.

        The legacy ``accounts.api_key`` column no longer exists (migration 023);
        all keys live in ``account_api_keys`` and are returned as-is.

        When ``records`` is provided (e.g. a single batched lookup for all
        suppliers), it is used directly to avoid one query per supplier (P2);
        otherwise the keys are loaded for this single supplier.
        """
        if records is None and self.account_repo is not None:
            records = self.account_repo.find_all_api_keys(supplier["id"])
        records = records or []
        supplier["api_keys"] = [r["api_key"] for r in records]
        supplier["api_key_records"] = records

    def _enrich_quota(self, supplier: dict):
        """Enrich a supplier dict with quota info from the appropriate strategy."""
        provider_type = supplier.get("provider_type", DEFAULT_PROVIDER_TYPE)
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

    @staticmethod
    def _extract_keys(entry: dict) -> list:
        """Extract the list of API key strings from a supplier dict.

        Prefers the structured ``api_key_records`` (preserves status/alias),
        then ``api_keys``, then falls back to a single legacy ``api_key`` for
        backward compatibility with older exports.
        """
        records = entry.get("api_key_records")
        if records:
            return [r.get("api_key", "").strip() for r in records
                    if r.get("api_key", "").strip()]
        keys = [k.strip() for k in (entry.get("api_keys") or []) if k and k.strip()]
        if keys:
            return keys
        single = (entry.get("api_key") or "").strip()
        return [single] if single else []

    def create_supplier(self, name: str, base_url: str,
                        provider_type: str = DEFAULT_PROVIDER_TYPE,
                        api_keys: list = None, api_key_records: list = None,
                        anthropic_base_url: str = "",
                        anthropic_auth_style: str = "anthropic",
                        anthropic_stream_protocol: str = DEFAULT_ANTHROPIC_STREAM_PROTOCOL) -> dict:
        """Create a supplier. Requires at least one API key (stored in account_api_keys).

        ``anthropic_base_url`` optionally points the Anthropic-native protocol at
        a different upstream than ``base_url`` (dual-protocol suppliers).
        ``anthropic_auth_style`` is the auth scheme used when calling that
        supplier's Anthropic endpoint (``x-api-key`` for native Anthropic,
        ``bearer`` for suppliers like SenseTime that expose an Anthropic-shaped
        ``/v1/messages`` but still require ``Authorization: Bearer``).
        ``anthropic_stream_protocol`` selects the upstream protocol for Anthropic
        requests (``native`` / ``openai`` / ``auto``).
        """
        if api_key_records:
            keys = [r.get("api_key", "").strip() for r in api_key_records
                    if r.get("api_key", "").strip()]
            created = self.account_repo.create(
                name, base_url, provider_type=provider_type, api_keys=keys,
                anthropic_base_url=anthropic_base_url,
                anthropic_auth_style=anthropic_auth_style,
                anthropic_stream_protocol=anthropic_stream_protocol,
            )
            if self.account_repo is not None:
                self.account_repo.replace_api_keys_with_records(
                    created["id"], api_key_records
                )
            return created

        keys = [k.strip() for k in (api_keys or []) if k and k.strip()]
        if not keys:
            raise ValueError("At least one API key is required")
        return self.account_repo.create(
            name, base_url, provider_type=provider_type, api_keys=keys,
            anthropic_base_url=anthropic_base_url,
            anthropic_auth_style=anthropic_auth_style,
            anthropic_stream_protocol=anthropic_stream_protocol,
        )

    def update_supplier(self, supplier_id: int, **kwargs) -> dict:
        api_keys = kwargs.pop("api_keys", None)
        api_key_records = kwargs.pop("api_key_records", None)
        updated = self.account_repo.update(supplier_id, **kwargs)
        if api_key_records is not None and updated and self.account_repo is not None:
            self.account_repo.replace_api_keys_with_records(supplier_id, api_key_records)
        elif api_keys is not None and updated and self.account_repo is not None:
            self.account_repo.replace_api_keys(supplier_id, api_keys)
        return updated

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

    # ── Account API Keys ──

    def get_api_keys(self, supplier_id: int) -> list:
        """List all API keys for a supplier."""
        if self.account_repo is None:
            return []
        return self.account_repo.find_api_keys(supplier_id)

    def add_api_key(self, supplier_id: int, api_key: str) -> dict:
        """Add an additional API key for a supplier."""
        if self.account_repo is None:
            raise NotImplementedError("Account repo not configured")
        return self.account_repo.add_api_key(supplier_id, api_key)

    def update_api_key_status(self, key_id: int, status: str) -> dict:
        """Freeze or unfreeze an API key."""
        if self.account_repo is None:
            raise NotImplementedError("Account repo not configured")
        return self.account_repo.update_api_key_status(key_id, status)

    def delete_api_key(self, key_id: int) -> bool:
        """Delete an API key."""
        if self.account_repo is None:
            return False
        return self.account_repo.delete_api_key(key_id)

    def get_api_key_by_id(self, key_id: int) -> dict:
        """Get a specific API key by ID."""
        if self.account_repo is None:
            return None
        return self.account_repo.find_api_key_by_id(key_id)

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
            DEFAULT_PROVIDER_TYPE: create_strategy(
                "header_based",
                quota_updater=self.quota_updater,
                quota_repository=self.quota_repo,
            ),
            "sensetime": create_strategy(
                "fixed_window", db=self.db,
                rate_limit_cache=self.rate_limit_cache,
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
                        rate_limit_cache=self.rate_limit_cache,
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
        """Upsert a supplier's model catalog (no FK CASCADE — bindings preserved).

        The repository now uses ``INSERT ... ON CONFLICT DO UPDATE`` so that
        ``supplier_models`` rows already referenced by
        ``mapping_models.supplier_model_id`` are updated in place rather than
        deleted-and-reinserted.  Routing bindings are therefore preserved
        across supplier edits.
        """
        if self.supplier_model_repo is None:
            return []
        self.supplier_model_repo.bulk_upsert(supplier_id, models)
        return self.supplier_model_repo.find_by_supplier(supplier_id)

    # ── Supplier Import / Export ──

    def export_suppliers(self) -> dict:
        """Export all suppliers with their models as a structured dict.

        The returned dict is JSON/YAML-serializable and includes metadata
        (version, exported_at) plus the full supplier list including models
        and API key records (with status).
        """
        suppliers = self.account_repo.find_all()
        ids = [sup["id"] for sup in suppliers]
        # Batch-load models + API keys for all suppliers in one query each
        # instead of one query per supplier (P6 / N+1).
        models_by_id = {}
        if self.supplier_model_repo is not None:
            try:
                models_by_id = self.supplier_model_repo.find_by_supplier_batch(ids) or {}
            except Exception:
                models_by_id = {}
        keys_by_id = {}
        if self.account_repo is not None:
            try:
                keys_by_id = self.account_repo.find_api_keys_by_account_ids(ids) or {}
            except Exception:
                keys_by_id = {}
        result = []
        for sup in suppliers:
            models = models_by_id.get(sup["id"], [])
            key_records = keys_by_id.get(sup["id"], [])
            result.append({
                "name": sup.get("name", ""),
                "api_key": (key_records[0]["api_key"] if key_records else ""),
                "base_url": sup.get("base_url", ""),
                "provider_type": sup.get("provider_type", DEFAULT_PROVIDER_TYPE),
                "status": sup.get("status", "active"),
                "models": [
                    {
                        "model_name": m.get("model_name", ""),
                        "model_type": m.get("model_type", "text"),
                        "context_length": m.get("context_length"),
                    }
                    for m in models
                ],
                "api_key_records": key_records,
            })
        return {
            "version": "1.0",
            "exported_at": _tz_now().isoformat(timespec="seconds"),
            "suppliers": result,
        }

    def export_config(self) -> dict:
        """Export full system config: suppliers, provider_types, mappings."""
        suppliers = self.account_repo.find_all()
        ids = [sup["id"] for sup in suppliers]
        # Batch-load models + API keys for all suppliers in one query each
        # instead of one query per supplier (P6 / N+1).
        models_by_id = {}
        if self.supplier_model_repo is not None:
            try:
                models_by_id = self.supplier_model_repo.find_by_supplier_batch(ids) or {}
            except Exception:
                models_by_id = {}
        keys_by_id = {}
        if self.account_repo is not None:
            try:
                keys_by_id = self.account_repo.find_api_keys_by_account_ids(ids) or {}
            except Exception:
                keys_by_id = {}
        supplier_list = []
        for sup in suppliers:
            models = models_by_id.get(sup["id"], [])
            key_records = keys_by_id.get(sup["id"], [])
            supplier_list.append({
                "name": sup.get("name", ""),
                "api_key": (key_records[0]["api_key"] if key_records else ""),
                "base_url": sup.get("base_url", ""),
                "provider_type": sup.get("provider_type", DEFAULT_PROVIDER_TYPE),
                "status": sup.get("status", "active"),
                "models": [
                    {
                        "model_name": m.get("model_name", ""),
                        "model_type": m.get("model_type", "text"),
                        "context_length": m.get("context_length"),
                    }
                    for m in models
                ],
                "api_key_records": key_records,
            })

        provider_types = self.get_provider_types()
        mappings = self.get_mappings()

        return {
            "version": "1.0",
            "exported_at": _tz_now().isoformat(timespec="seconds"),
            "suppliers": supplier_list,
            "provider_types": provider_types,
            "mappings": mappings,
        }

    def import_suppliers(self, data: dict, strategy: str = "skip") -> dict:
        """Import full system config from a previously exported data structure.

        Handles three sections when present: ``provider_types``, ``suppliers``,
        and ``mappings``.  Each section is processed in dependency order so that
        provider types exist before suppliers are created, and suppliers exist
        before mappings are resolved.

        Args:
            data: Parsed dict from JSON/YAML import (as produced by export_config).
            strategy: How to handle duplicate names — "skip" (default) or "overwrite".

        Returns:
            Stats dict: {provider_types: {created, skipped, updated, errors},
                         suppliers: {created, skipped, updated, errors, total},
                         mappings: {created, skipped, updated, errors},
                         errors}
        """
        if not isinstance(data, dict):
            raise ValueError("无效的导入格式：根对象必须是字典")

        if "suppliers" not in data:
            raise ValueError("无效的导入格式：缺少 'suppliers' 字段")

        entries = data["suppliers"]
        if not isinstance(entries, list):
            raise ValueError("无效的导入格式：'suppliers' 必须是列表")

        stats = {
            "provider_types": {"created": 0, "skipped": 0, "updated": 0, "errors": []},
            "suppliers": {"created": 0, "skipped": 0, "updated": 0, "errors": [], "total": len(entries)},
            "mappings": {"created": 0, "skipped": 0, "updated": 0, "errors": []},
            "errors": [],
        }

        # ── 1. Import provider_types first ──
        if "provider_types" in data and isinstance(data["provider_types"], list):
            self._import_provider_types(data["provider_types"], strategy, stats["provider_types"])
            self.rebuild_rate_limit_strategies()

        # ── 2. Import suppliers ──
        for idx, entry in enumerate(entries):
            try:
                # ── Validate required fields ──
                name = entry.get("name", "").strip()
                base_url = entry.get("base_url", "").strip()
                # Keys can come from api_key_records / api_keys / legacy api_key.
                api_key_records = entry.get("api_key_records")
                keys = self._extract_keys(entry)
                if not name or not base_url or not keys:
                    raise ValueError("缺少必填字段 name / base_url / 至少一个 api_key")

                status = entry.get("status", "active")
                provider_type = entry.get("provider_type", DEFAULT_PROVIDER_TYPE)
                models = entry.get("models", [])

                # ── Check for duplicate by name ──
                existing = self.account_repo.find_by_name(name)
                if existing:
                    if strategy == "skip":
                        stats["suppliers"]["skipped"] += 1
                        continue
                    elif strategy == "overwrite":
                        self.account_repo.update(
                            existing["id"],
                            base_url=base_url,
                            status=status,
                            provider_type=provider_type,
                        )
                        if api_key_records and self.account_repo is not None:
                            self.account_repo.replace_api_keys_with_records(existing["id"], api_key_records)
                        elif self.account_repo is not None:
                            self.account_repo.replace_api_keys(existing["id"], keys)
                        if self.supplier_model_repo is not None and isinstance(models, list):
                            self._safe_bulk_models(existing["id"], models)
                        stats["suppliers"]["updated"] += 1
                        continue
                    else:
                        raise ValueError(f"未知的处理策略: {strategy}")

                # ── Create new supplier ──
                created = self.account_repo.create(
                    name=name, base_url=base_url,
                    status=status, provider_type=provider_type,
                    api_keys=keys,
                )
                if api_key_records and self.account_repo is not None:
                    self.account_repo.replace_api_keys_with_records(created["id"], api_key_records)
                if self.supplier_model_repo is not None and isinstance(models, list):
                    self._safe_bulk_models(created["id"], models)
                stats["suppliers"]["created"] += 1

            except Exception as e:
                stats["suppliers"]["errors"].append(f"第 {idx + 1} 项 ({entry.get('name', '?')}): {str(e)}")

        # ── 3. Import mappings last ──
        if "mappings" in data and isinstance(data["mappings"], list):
            self._import_mappings(data["mappings"], strategy, stats["mappings"])

        # ── Consolidate top-level errors ──
        for section in ("provider_types", "suppliers", "mappings"):
            stats["errors"].extend(stats[section]["errors"])

        return stats

    def _import_provider_types(self, types: list, strategy: str, stats: dict) -> None:
        """Import provider types from exported data."""
        if self.provider_type_repo is None:
            stats["errors"].append("provider_type_repo 未配置，跳过供应商类型导入")
            return

        for idx, pt in enumerate(types):
            try:
                type_key = pt.get("type_key", "").strip()
                if not type_key:
                    raise ValueError("缺少必填字段 type_key")

                existing = self.provider_type_repo.find_by_type_key(type_key)
                if existing:
                    if strategy == "skip":
                        stats["skipped"] += 1
                        continue
                    if strategy == "overwrite":
                        self.provider_type_repo.update(
                            existing["id"],
                            name=pt.get("name", ""),
                            description=pt.get("description", ""),
                            strategy_type=pt.get("strategy_type", "header_based"),
                            config=pt.get("config") or {},
                            color=pt.get("color", "#89b4fa"),
                        )
                        stats["updated"] += 1
                        continue
                    else:
                        raise ValueError(f"未知的处理策略: {strategy}")

                self.provider_type_repo.create(
                    type_key=type_key,
                    name=pt.get("name", ""),
                    description=pt.get("description", ""),
                    strategy_type=pt.get("strategy_type", "header_based"),
                    config=pt.get("config") or {},
                    color=pt.get("color", "#89b4fa"),
                    built_in=bool(pt.get("built_in")),
                )
                stats["created"] += 1

            except Exception as e:
                stats["errors"].append(f"第 {idx + 1} 项 ({pt.get('type_key', '?')}): {str(e)}")

    def _import_mappings(self, mappings: list, strategy: str, stats: dict) -> None:
        """Import model mappings from exported data."""
        if self.mapping_repo is None:
            stats["errors"].append("mapping_repo 未配置，跳过映射导入")
            return

        for idx, m in enumerate(mappings):
            try:
                alias_name = m.get("alias_name", "").strip()
                if not alias_name:
                    raise ValueError("缺少必填字段 alias_name")

                existing_rows = self.mapping_repo.find_by_alias(alias_name)
                if existing_rows:
                    if strategy == "skip":
                        stats["skipped"] += 1
                        continue
                    elif strategy == "overwrite":
                        self.mapping_repo.update(
                            alias_name,
                            actual_model_id=m.get("actual_model_id", alias_name),
                            description=m.get("description", ""),
                            status=m.get("status", "active"),
                        )
                        stats["updated"] += 1
                        continue
                    else:
                        raise ValueError(f"未知的处理策略: {strategy}")

                self.mapping_repo.create(
                    alias_name=alias_name,
                    actual_model_id=m.get("actual_model_id", alias_name),
                    description=m.get("description", ""),
                    status=m.get("status", "active"),
                )
                stats["created"] += 1

            except Exception as e:
                stats["errors"].append(f"第 {idx + 1} 项 ({m.get('alias_name', '?')}): {str(e)}")

        # Mapping table changed — drop the cached /v1/models list (P3).
        invalidate_models_cache()

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
        result = self.mapping_repo.create(alias_name, actual_model_id, description, status)
        invalidate_models_cache()
        return result

    def update_mapping(self, alias_name: str, **kwargs):
        """Update mapping fields. Supported: actual_model_id, description, status."""
        result = self.mapping_repo.update(alias_name, **kwargs)
        invalidate_models_cache()
        return result

    def toggle_mapping_status(self, alias_name: str):
        """Toggle mapping status between 'active' and 'disabled'."""
        result = self.mapping_repo.toggle_status(alias_name)
        invalidate_models_cache()
        return result

    def bulk_update_mappings(self, mappings: dict):
        self.mapping_repo.bulk_upsert(mappings)
        invalidate_models_cache()

    def delete_mapping(self, alias_name: str):
        result = self.mapping_repo.delete_by_alias(alias_name)
        invalidate_models_cache()
        return result

    def rename_mapping(self, old_alias: str, new_alias: str):
        result = self.mapping_repo.rename(old_alias, new_alias)
        invalidate_models_cache()
        return result

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
        raw = self.config_repo.get("log_retention_hours") or "1"
        try:
            hours = float(raw)
        except (ValueError, TypeError):
            hours = 1.0
        # Guard against non-positive values that would wipe all logs
        if hours <= 0:
            hours = 1.0

        # IMPORTANT: request_logs.timestamp is stored as UTC (DB column default
        # CURRENT_TIMESTAMP), and routes.py writes request_start/end_time in UTC
        # too. The cutoff MUST therefore be computed in UTC to match. Using the
        # project timezone (Asia/Shanghai) here would shift the cutoff +8h and
        # wrongly delete all logs from the last 8 hours.
        cutoff = (
            datetime.datetime.now(_UTC)
            - datetime.timedelta(hours=hours)
        ).strftime("%Y-%m-%d %H:%M:%S")

        deleted = self.log_repo.delete_older_than(cutoff)
        if deleted > 0:
            logger.info(
                "Cleaned up %d log entries older than %s (retention=%sh)",
                deleted, cutoff, raw,
            )
            # SQLite DELETE 只把页标记为空闲，文件不会变小；只有在真正删除
            # 行之后才执行 VACUUM 回收磁盘空间。注意：不能在「无删除」分支做，
            # 否则每个空闲周期都会无谓地全量重建库文件（且真实删除时反而从不回收）。
            db = self.db or getattr(self.log_repo, "db", None)
            if db is not None:
                try:
                    db.vacuum()
                except Exception as exc:
                    logger.warning("VACUUM after log cleanup failed: %s", exc)
        else:
            logger.info(
                "Log cleanup: nothing to clean (cutoff=%s, retention=%sh)",
                cutoff, raw,
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

        # Batch-load all bound supplier accounts once instead of one query per
        # binding (P5 / N+1).
        sids = [b.get("supplier_id") for b in bound if b.get("supplier_id") is not None]
        acc_by_id = {}
        if sids and self.account_repo is not None:
            try:
                acc_by_id = self.account_repo.find_by_ids(sids) or {}
            except Exception:
                acc_by_id = {}
        for b in bound:
            sid = b.get("supplier_id")
            if sid is None:
                continue
            acc = acc_by_id.get(sid)
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

        # input_tokens is the full prompt size (see normalize_cache_usage), so
        # the denominator is input alone.
        cache_hit_rate = round(
            totals["cache_tokens"] / totals["input_tokens"] * 100, 1
        ) if totals["input_tokens"] > 0 else 0.0

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
                    response_headers: str = None,
                    api_key_id: int = 0,
                    error_source: str = None) -> str:
        """Log a request and return its request_id."""
        from datetime import datetime, timezone

        # Defensive net for every caller: fold a cache portion that the upstream
        # reported outside input_tokens back into it, so the aggregated cache
        # hit rate can never exceed 100 %. No-op for upstreams that already
        # include the cache in input_tokens.
        input_tokens, cached_tokens, prompt_partial_cached = normalize_cache_usage(
            input_tokens, cached_tokens, prompt_partial_cached
        )

        request_id = f"req_{uuid.uuid4().hex[:8]}"
        # Primary request time at millisecond precision (UTC). The DB column
        # default CURRENT_TIMESTAMP only has second precision, so set it
        # explicitly here. Format stays fixed-width "YYYY-MM-DD HH:MM:SS.fff"
        # so lexicographic ordering / range filters remain correct.
        now = datetime.now(timezone.utc)
        ts = now.strftime("%Y-%m-%d %H:%M:%S.") + f"{now.microsecond // 1000:03d}"

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
            except (ValueError, TypeError):
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
            api_key_id=api_key_id,
            error_source=error_source,
            timestamp=ts,
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
        if not keys:
            return []
        today_start = today()
        # Batch-load today's usage for all client keys in one query instead of
        # one query per key (P4 / N+1).
        stats_map: dict = {}
        if self.log_repo is not None:
            try:
                stats_map = self.log_repo.query_stats_client_keys_batch(
                    today_start, [k["name"] for k in keys]
                ) or {}
            except Exception:
                logger.debug("Failed to batch-load client key usage", exc_info=True)
        for k in keys:
            s = stats_map.get(k["name"], {})
            k["today_requests"] = s.get("requests", 0) or 0
            k["today_input_tokens"] = s.get("input_tokens", 0) or 0
            k["today_output_tokens"] = s.get("output_tokens", 0) or 0
            k["today_cache_tokens"] = s.get("cached_tokens", 0) or 0
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

    def get_key_docs(self, key_id: int, base_url: str = None, anthropic_base_url: str = None):
        """Return integration meta-data for a client API key.

        Only dynamic data is returned — the rendering is done in the frontend
        to keep documentation content, code snippets, and error-table content
        in a single source of truth (Guide.vue / KeyDetailPanel).

        Args:
            key_id: Client API key primary key.
            base_url: OpenAI entry base URL (e.g. ``https://example.com/openai/v1``).
            anthropic_base_url: Anthropic entry base URL (e.g. ``.../anthropic/v1``).
        """
        if self.client_key_repo is None:
            return {}
        key = self.client_key_repo.find_by_id(key_id)
        if not key:
            return {}
        if not base_url:
            base_url = "https://your-domain.com/openai/v1"
        if not anthropic_base_url:
            anthropic_base_url = "https://your-domain.com/anthropic/v1"
        return {"key_value": key["key_value"],
                "base_url": base_url,
                "anthropic_base_url": anthropic_base_url}

    # ── Model Quotas ──

    def _get_account_rate_windows(self, account_id: str) -> dict:
        """Read raw window counters keyed by ``(model_name, key_id)``.

        Returns the authoritative window counters for an account straight from
        ``account_rate_windows``. Going through this table (instead of the
        strategy object) is intentional: at request time SenseTime counts under
        an aliased model name, and the admin strategy instance can differ from
        the request-time one — both would make the strategy methods unreliable.

        Since the per-model window is now keyed per API key, a single model may
        have several rows (one per ``key_id``); the display layer aggregates them.
        """
        if self.db is None:
            return {}
        try:
            with self.db.get_connection() as conn:
                rows = conn.execute(
                    "SELECT model_name, key_id, window_start, request_count "
                    "FROM account_rate_windows WHERE account_id = ?",
                    (account_id,),
                ).fetchall()
            return {
                (r["model_name"], r["key_id"]): (r["window_start"], r["request_count"])
                for r in rows
            }
        except Exception:
            return {}

    def get_model_quotas(self, days: int = 0, key_id: int | None = None):
        """Get model-level quota info by supplier + model.

        Reads from model_quotas table (populated from modelscope-ratelimit-model-requests-* headers).
        Falls back to request_logs for token usage if no model quota entry exists.

        Args:
            days: 0 = today only, otherwise past N days. When >0, token usage
                  and success rate are aggregated from the stats table over the
                  requested range instead of from model_quotas cumulative fields.
            key_id: when not None, filter request stats by this api_key_id (from
                    ``account_api_keys``; primary key is ``0``). Quota and window
                    data are also scoped to this key (model_quotas rows filtered
                    by key_id, window counters scoped to the key, max_requests
                    shows the per-key limit instead of key-count × base).

        Returns a list of dicts:
        - supplier_id, supplier_name, account_id
        - model_name, model_type
        - quota_remaining, quota_limit (from model_quotas table)
        - today_input_tokens, today_output_tokens (from model_quotas or request_logs)
        - is_unavailable
        - request_count, success_count, success_rate (from stats table over range)
        - strategy_type, window_seconds, max_requests
          (the "按模型窗口" policy; from the fixed-window strategy counters.
           max_requests == window_quota_limit == the window's request cap)
        - window_quota_remaining, window_quota_limit (live remaining requests)
        - has_custom_window, window_override
          (whether this model has a per-model override in provider_types.config)
        """
        if self.quota_repo is None or self.supplier_model_repo is None:
            return []

        # 前端传的是 account_api_keys.id（自增主键），而所有内部表（request_logs、
        # model_quotas、account_quotas、account_rate_windows）都用逻辑 key_id
        # （0 = 主 key，1 = 第二 key...）。在此处转换。
        if key_id is not None:
            key_id = self.account_repo.api_key_id_to_logical(key_id)

        # 计算时间范围（days=0 = 今日，否则过去 N 天）
        if days and days > 0:
            from datetime import timedelta
            _range_end = _tz_now().strftime("%Y-%m-%d %H:%M:%S")
            _range_start = (_tz_now() - timedelta(days=days)).strftime("%Y-%m-%d 00:00:00")
        else:
            _range_start, _range_end = today_range()

        # Get all suppliers
        suppliers = self.account_repo.find_all()

        # Get supplier-level quota info for unavailable_models — batch load
        # once instead of one query per supplier (P1 / N+1).
        account_ids_all = [sup["account_id"] for sup in suppliers]
        quota_info_batch = {}
        if self.quota_repo is not None and account_ids_all:
            try:
                quota_info_batch = self.quota_repo.get_account_info_batch(account_ids_all, key_id=key_id) or {}
            except Exception:
                quota_info_batch = {}

        supplier_quota_map = {}
        for sup in suppliers:
            aid = sup["account_id"]
            info = quota_info_batch.get(aid)
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

        # Build provider-type → window-strategy map once, so the per-model
        # window config (provider_types.config["models"]) can be reflected onto
        # each model row. Without this, the "按模型窗口" policy lives only in the
        # strategy internals / provider-type config and never shows on the model.
        pt_map = {}
        if self.provider_type_repo is not None:
            # Skip only the offending provider-type row rather than discarding
            # the whole map — otherwise a single malformed row would silently
            # downgrade every supplier to "被动" (no window strategy shown).
            for pt in self.provider_type_repo.find_all():
                try:
                    cfg = pt.get("config") or {}
                    pt_map[pt["type_key"]] = {
                        "strategy_type": pt.get("strategy_type"),
                        "models": cfg.get("models", {}) or {},
                        "window_seconds": cfg.get("window_seconds"),
                        "max_requests": cfg.get("max_requests"),
                    }
                except Exception:
                    continue

        # Batch-load model quotas + supplier model catalogs once (P1 / N+1)
        model_quotas_all = {}
        models_by_supplier = {}
        if suppliers:
            if self.quota_repo is not None:
                try:
                    model_quotas_all = self.quota_repo.get_model_quotas_batch(
                        [sup["account_id"] for sup in suppliers], key_id=key_id
                    ) or {}
                except Exception:
                    model_quotas_all = {}
            if self.supplier_model_repo is not None:
                try:
                    models_by_supplier = self.supplier_model_repo.find_by_supplier_batch(
                        [sup["id"] for sup in suppliers]
                    ) or {}
                except Exception:
                    models_by_supplier = {}

        result = []
        for sup in suppliers:
            sid = sup["id"]
            account_id = sup["account_id"]
            sup_name = sup.get("name", "")

            # Resolve this supplier's window strategy + per-model overrides
            provider_type = sup.get("provider_type", DEFAULT_PROVIDER_TYPE)
            pt_info = pt_map.get(provider_type, {})
            strategy = self.rate_limit_strategies.get(provider_type)
            strategy_type = pt_info.get("strategy_type")
            model_overrides = pt_info.get("models", {}) or {}

            # Infer strategy type when not declared via the provider-type table
            # (e.g. the built-in "sensetime" fallback strategy).
            if strategy is not None and strategy_type is None:
                try:
                    from services.providers.per_model import PerModelFixedWindowStrategy
                    from services.providers.sensetime import SenseTimeStrategy
                    if isinstance(strategy, PerModelFixedWindowStrategy):
                        strategy_type = "fixed_window_per_model"
                    elif isinstance(strategy, SenseTimeStrategy):
                        strategy_type = "fixed_window"
                except Exception:
                    pass

            # Get model-level quotas for this supplier (already loaded in batch)
            model_quotas = model_quotas_all.get(account_id, [])
            model_quota_map = {m["model_name"]: m for m in model_quotas}

            # Get all models for this supplier (already loaded in batch)
            models = models_by_supplier.get(sid, [])

            # Pre-fetch raw window counters for this account directly from
            # account_rate_windows — the authoritative source of truth. We read
            # the table ourselves instead of via the strategy object because:
            #  (1) at request time SenseTime counts under an aliased model name
            #      (e.g. "sense"), so a per-configured-model lookup would miss it;
            #  (2) the admin strategy instance can differ from the request-time
            #      one, so get_quota_info()/get_model_quota_info() are fragile.
            # Reading the DB directly is robust to both.
            raw_windows = self._get_account_rate_windows(account_id)

            # 反向别名映射：目录模型名 -> 请求时使用的客户端别名（virtual_model）。
            # 这样即使窗口曾以别名（如 "sense"）计数，也能正确关联回目录模型行。
            model_to_alias = {}
            try:
                with self.db.get_connection() as _conn:
                    _arows = _conn.execute(
                        "SELECT DISTINCT model, virtual_model FROM request_stats_minute "
                        "WHERE account_id = ? AND virtual_model IS NOT NULL AND virtual_model != ''",
                        (account_id,),
                    ).fetchall()
                    for _r in _arows:
                        model_to_alias.setdefault(_r["model"], set()).add(_r["virtual_model"])
            except Exception:
                model_to_alias = {}

            # 本供应商目录内的全部模型名 + 它们的全部别名。用于判断某个窗口
            # key 是否"属于某个具体模型"——若是，则绝不能作为供应商级共用
            # 计数器回退给其他模型（否则 A 模型的计数会串到 B 模型的行上）。
            _catalog_names = {mm.get("model_name") for mm in models if mm.get("model_name")}
            _all_alias_keys = set()
            for _aliases in model_to_alias.values():
                _all_alias_keys.update(_aliases)

            # ── Per-account batch stats (P1): fetch every model's today-token
            # usage + range aggregate in ONE query each instead of one per model
            # (the old code issued N×M queries inside this loop).  Memoize the
            # alias lookup + active-key count the same way.
            model_names = [m.get("model_name") for m in models if m.get("model_name")]
            token_today_map = {}
            agg_map = {}
            agg_by_key_map = {}
            if self.log_repo is not None and model_names:
                try:
                    token_today_map = self.log_repo.query_stats_today_token_usage_batch(
                        account_id, model_names, *today_range()
                    ) or {}
                except Exception:
                    token_today_map = {}
                try:
                    agg_map = self.log_repo.query_stats_model_aggregate_batch(
                        account_id, model_names, _range_start, _range_end
                    ) or {}
                except Exception:
                    agg_map = {}
                if key_id is not None:
                    try:
                        agg_by_key_map = self.log_repo.query_stats_model_aggregate_by_key_batch(
                            account_id, model_names, key_id, _range_start, _range_end
                        ) or {}
                    except Exception:
                        agg_by_key_map = {}

            # active key count is constant per supplier — compute once, not per model
            key_count = 1
            try:
                key_count = self.account_repo.count_active_keys(account_id)
            except Exception:
                key_count = 1
            alias_cache: dict = {}

            for m in models:
                model_name = m.get("model_name", "")
                model_type = m.get("model_type", "text")

                # Get model-level quota from model_quotas table
                mq = model_quota_map.get(model_name, {})
                quota_remaining = mq.get("quota_remaining", 0)
                quota_limit = mq.get("quota_limit", 0)
                today_input = mq.get("total_input_tokens", 0) or 0
                today_output = mq.get("total_output_tokens", 0) or 0
                today_cached = mq.get("total_cached_tokens", 0) or 0

                # Fallback: if no model quota entry yet, derive from request_logs.
                # cached_tokens is always read from request_stats_minute because the
                # model_quotas table lacks a total_cached_tokens column — without this
                # fallback the cache column would always show 0.
                if quota_limit == 0 and today_input == 0 and today_output == 0:
                    _ti, _to, _tc = token_today_map.get(model_name, (0, 0, 0))
                    today_input, today_output, today_cached = _ti, _to, _tc
                elif today_cached == 0:
                    # Model has usage data in model_quotas but cached_tokens was
                    # never persisted there — fetch it from the stats table.
                    _ti, _to, _tc = token_today_map.get(model_name, (0, 0, 0))
                    today_cached = _tc or today_cached

                # 按时间范围查询请求数/成功数/成功率（stats 表）；
                # 当指定 key_id 时改用 request_logs 按该 key 聚合
                # （request_stats_minute 不区分 key）。两者均来自本供应商的
                # 批量预取结果，避免每个模型再发一次查询（P1 / N+1）。
                _requests = 0
                _success = 0
                _success_rate = None
                _inp_s = _out_s = _cached_s = 0
                try:
                    if key_id is not None:
                        _inp_s, _out_s, _cached_s, _req_s, _suc_s = \
                            agg_by_key_map.get(model_name, (0, 0, 0, 0, 0))
                    else:
                        _inp_s, _out_s, _cached_s, _req_s, _suc_s = \
                            agg_map.get(model_name, (0, 0, 0, 0, 0))
                    _requests = _req_s
                    _success = _suc_s
                    _success_rate = round(_suc_s / _req_s * 100, 1) if _req_s else None
                except Exception:
                    pass
                # 指定 key 时：token 用量永远取按该 key 聚合的结果（request_logs 的
                # agg_by_key_map），否则会回退到全供应商级的 token_today_map /
                # model_quotas 累计值，导致所有 key 的用量显示成一模一样。days>0 时
                # 同理走按范围聚合。
                if key_id is not None:
                    today_input = _inp_s
                    today_output = _out_s
                    today_cached = _cached_s
                elif days and days > 0:
                    today_input = _inp_s
                    today_output = _out_s
                    today_cached = _cached_s

                is_unavailable = model_name in supplier_quota_map.get(account_id, {}).get("unavailable_models", set())

                # Per-model window strategy info (from the fixed-window counters in
                # account_rate_windows, NOT the header-driven model_quotas table).
                # This is what surfaces the "按模型窗口" policy on the model row.
                #  - genuine per-model strategy: counter keyed by the configured model name
                #  - SenseTime aliases every model to one underlying name, so if no row
                #    matches the configured name we fall back to the single account row
                #    (supplier-wide counter).
                win = {}
                if strategy_type in ("fixed_window", "fixed_window_per_model", "sensetime"):
                    # window config: per-model override > provider-type default > built-in
                    win_cfg = model_overrides.get(model_name) or {}
                    window_seconds = win_cfg.get("window_seconds") or pt_info.get("window_seconds") or 18000
                    max_requests = win_cfg.get("max_requests") or pt_info.get("max_requests") or 1500
                    # 配额上限 × 活跃 key 数：每个 key 在上游持有独立配额，因此
                    # 多 key 账户的有效窗口额度 = 配置上限 × N，与拦截侧一致。
                    # 计数语义与 AliasRouter 候选一致（主密钥 + 活跃 account_api_keys）。
                    # 当指定 key_id 时，显示该 key 的单 key 上限，不乘 key 数。
                    try:
                        if key_id is not None:
                            max_requests = max_requests  # 单 key 上限
                        else:
                            max_requests = max_requests * max(1, key_count)
                    except Exception:
                        pass
                    # 计数 key 以真实模型 ID (actual_model_id) 写入（见 routes.py
                    # check_rate_limit），此处 model_name 是模型目录名，往往是
                    # mapping 的 alias，两者可能不同。优先直接匹配，否则尝试把
                    # model_name 解析为 actual_model_id 再匹配，避免“按模型”窗口
                    # 因名字不一致而始终显示满额。
                    match_keys = [model_name]
                    if self.mapping_repo is not None and model_name:
                        _mrows = alias_cache.get(model_name)
                        if _mrows is None:
                            _mrows = self.mapping_repo.find_by_alias(model_name)
                            alias_cache[model_name] = _mrows
                        if _mrows:
                            match_keys.append(_mrows[0].get("actual_model_id"))
                    # 也尝试该目录模型在 stats 中记录过的客户端别名（如 "sense"）
                    for _alias in model_to_alias.get(model_name, set()):
                        if _alias and _alias not in match_keys:
                            match_keys.append(_alias)

                    # 滑动窗口「已用」= 当前时刻往前 window_seconds 内的请求数。
                    # 优先从内存 RateLimitCache 取实时滑动计数（与拦截同源、实时）；
                    # 若内存中无该窗口（如刚重启且尚未有请求），回退到 DB 快照。
                    sliding_count = None
                    if self.rate_limit_cache is not None:
                        _counts = []
                        for _k in match_keys:
                            try:
                                _info = self.rate_limit_cache.get_model_count_across_keys(
                                    account_id, _k, window_seconds, max_requests,
                                    key_id=key_id,
                                )
                            except Exception:
                                _info = None
                            if _info and _info.get("request_count") is not None:
                                _counts.append(_info["request_count"])
                        if _counts:
                            sliding_count = max(_counts)

                    if sliding_count is None:
                        # raw_windows is keyed by (model_name, key_id). When
                        # key_id is specified, scope to that key only.
                        cnt = 0
                        matched = False
                        for _mn in match_keys:
                            for (_rmn, _rkid), (_ws, _rc) in raw_windows.items():
                                if _rmn == _mn and (key_id is None or _rkid == key_id):
                                    cnt += _rc
                                    matched = True
                        if matched:
                            sliding_count = cnt
                        else:
                            # Supplier-wide fallback (e.g. SenseTime aliases every
                            # model to one "__global__" counter). Each key now holds
                            # its own window counter (per-key), so the supplier-wide
                            # used count is the per-key sum — sum across all keys
                            # that share that aliased row. Only fall back when the
                            # matched model is NOT itself another specific catalog
                            # model (otherwise model A's counter would bleed onto
                            # model B's row).
                            _global_rows = [
                                _rc for (_rmn, _rkid), (_ws, _rc) in raw_windows.items()
                                if _rmn == "__global__"
                                and (key_id is None or _rkid == key_id)
                            ]
                            if _global_rows:
                                sliding_count = sum(_global_rows)
                            elif len(raw_windows) == 1:
                                _only_key = next(iter(raw_windows))
                                _belongs_to_other = (
                                    _only_key[0] in _catalog_names and _only_key[0] != model_name
                                )
                                if not _belongs_to_other:
                                    sliding_count = next(iter(raw_windows.values()))[1]
                                else:
                                    sliding_count = 0
                            else:
                                sliding_count = 0

                    remaining = max(0, max_requests - sliding_count)
                    win = {
                        "window_seconds": window_seconds,
                        "quota_limit": max_requests,
                        "quota_remaining": remaining,
                    }

                has_custom_window = model_name in model_overrides
                window_override = model_overrides.get(model_name)

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
                    "today_cached_tokens": today_cached,
                    "is_unavailable": is_unavailable,
                    "request_count": _requests,
                    "success_count": _success,
                    "success_rate": _success_rate,
                    # ── 按模型窗口策略透出 ──
                    "strategy_type": strategy_type,
                    "window_seconds": win.get("window_seconds"),
                    # Window request limit. The strategy methods don't expose a
                    # separate "max_requests" key, so surface the window limit
                    # (== quota_limit) directly instead of an always-None lookup.
                    "max_requests": win.get("quota_limit"),
                    "window_quota_remaining": win.get("quota_remaining"),
                    "window_quota_limit": win.get("quota_limit"),
                    "has_custom_window": has_custom_window,
                    "window_override": window_override,
                })

        return result

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

        # Cache hit rate: cached / input. input_tokens is the full prompt size —
        # normalize_cache_usage folds any upstream-reported cache portion that
        # sits outside input_tokens back in — so the denominator is input alone.
        cache_hit_rate = round(total_cached / total_input * 100, 1) if total_input > 0 else 0.0

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

        seconds == 0 means "today" mode: the window is the natural calendar day
        (00:00 → now, Shanghai time) with 24 hourly buckets (00:00 → 23:00,
        future hours stay 0); the previous window is yesterday's same clock span.

        Series buckets are epoch-aligned (bucket_start divisible by
        bucket_seconds) and span the bucket containing `start` through the one
        containing `end` inclusive, so len(series) is seconds // bucket or
        seconds // bucket + 1. The trailing bucket is usually still in
        progress; its qps is computed over its elapsed portion only.
        """
        import calendar
        import time
        from datetime import datetime, timedelta, timezone

        fmt = "%Y-%m-%d %H:%M:%S"
        now = datetime.now(TZ)

        raw_seconds = 300 if seconds is None else int(seconds)
        is_today = raw_seconds <= 0
        if is_today:
            # 今天模式：自然日 00:00 → 当前时刻，每小时一个桶
            bucket = 3600
            window_seconds = 0
            start_dt = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elapsed_seconds = max(1, int((now - start_dt).total_seconds()))
        else:
            seconds = max(60, min(raw_seconds, 2592000))
            bucket = self._WINDOW_BUCKET_MAP.get(seconds, max(1, seconds // 30))
            window_seconds = seconds
            start_dt = now - timedelta(seconds=seconds)
            elapsed_seconds = seconds

        start, end = start_dt.strftime(fmt), now.strftime(fmt)

        # Current window vs previous window (exclusive right bound: no overlap)
        cur = self.log_repo.query_stats_summarize(start, end)
        if is_today:
            # 较昨日同时段（昨天 00:00 → 昨天同一钟点）
            prev_start_dt = start_dt - timedelta(days=1)
            prev_end_dt = prev_start_dt + timedelta(seconds=elapsed_seconds)
            prev = self.log_repo.query_stats_summarize(
                prev_start_dt.strftime(fmt), prev_end_dt.strftime(fmt)
            )
        else:
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
        elif is_today:
            # 今天模式：固定全天 24 个整点（00:00 → 23:00），未到的小时保持 0
            first_epoch = int(start_dt.timestamp())
            n_buckets = 24
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

        # 过滤掉智能路由别名 —— 模型状态只显示真实供应商模型
        if self.mapping_repo is not None:
            alias_names = set()
            for _m in self.mapping_repo.find_all():
                _an = _m.get("alias_name", "")
                if _an:
                    alias_names.add(_an)
            if alias_names:
                models = [m for m in models if m.get("model") not in alias_names]

        return {
            "window_seconds": window_seconds,
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
                "qps": round(total / elapsed_seconds, 1),
                "avg_latency_ms": round(avg_latency) if avg_latency is not None else None,
                "delta": delta,
            },
            "prev": {
                "total": prev_total,
                "total_tokens": prev_tokens,
                "success_rate": prev_rate,
                "qps": round(prev_total / elapsed_seconds, 1),
                "avg_latency_ms": round(prev_avg) if prev_avg is not None else None,
            },
            "series": series,
            "status_codes": status_codes,
            "models": models,
        }
