"""Admin service for the management panel."""
import datetime
import uuid

from repositories.account_repository import AccountRepository
from repositories.client_api_key_repository import ClientApiKeyRepository
from repositories.config_repository import ConfigRepository
from repositories.log_repository import LogRepository
from repositories.mapping_repository import MappingRepository
from repositories.mapping_model_repository import MappingModelRepository
from repositories.quota_repository import QuotaRepository
from repositories.supplier_model_repository import SupplierModelRepository


class AdminService:
    """High-level admin operations."""

    def __init__(self, account_repo: AccountRepository,
                 mapping_repo: MappingRepository,
                 config_repo: ConfigRepository,
                 log_repo: LogRepository,
                 quota_repo: QuotaRepository = None,
                 supplier_model_repo: SupplierModelRepository = None,
                 mapping_model_repo: MappingModelRepository = None,
                 client_key_repo: ClientApiKeyRepository = None):
        self.account_repo = account_repo
        self.mapping_repo = mapping_repo
        self.config_repo = config_repo
        self.log_repo = log_repo
        self.quota_repo = quota_repo
        self.supplier_model_repo = supplier_model_repo
        self.mapping_model_repo = mapping_model_repo
        self.client_key_repo = client_key_repo

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
            "exported_at": datetime.datetime.now().isoformat(timespec="seconds"),
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
                        )
                        if self.supplier_model_repo is not None and isinstance(models, list):
                            self._safe_bulk_models(existing["id"], models)
                        stats["updated"] += 1
                        continue
                    else:
                        raise ValueError(f"未知的处理策略: {strategy}")

                # ── Create new supplier ──
                created = self.account_repo.create(
                    name=name, api_key=api_key, base_url=base_url, status=status
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

    def upsert_mapping(self, alias_name: str, actual_model_id: str):
        return self.mapping_repo.create(alias_name, actual_model_id)

    def bulk_update_mappings(self, mappings: dict):
        self.mapping_repo.bulk_upsert(mappings)

    def delete_mapping(self, alias_name: str):
        return self.mapping_repo.delete_by_alias(alias_name)

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
                from datetime import datetime
                def parse_ts(ts: str) -> float:
                    # Support both "YYYY-MM-DD HH:MM:SS" and "YYYY-MM-DDTHH:MM:SS" formats
                    ts = ts.replace(" ", "T")
                    # Try parsing with milliseconds
                    if "." in ts:
                        dt = datetime.fromisoformat(ts.replace("+00:00", ""))
                    else:
                        dt = datetime.fromisoformat(ts.replace("+00:00", ""))
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
        return request_id

    # ── Client API Keys ──

    def get_client_keys(self):
        """List all client API keys enriched with today's usage stats."""
        if self.client_key_repo is None:
            return []
        keys = self.client_key_repo.find_all()
        # Enrich with today's log stats
        today_start = datetime.datetime.now().strftime("%Y-%m-%d")
        for k in keys:
            k["today_requests"] = 0
            k["today_input_tokens"] = 0
            k["today_output_tokens"] = 0
            try:
                records, _ = self.log_repo.find_all(
                    page=0, page_size=10000,
                    client_key_name=k["name"],
                    start_time=today_start,
                )
                for r in records:
                    k["today_requests"] += 1
                    k["today_input_tokens"] += r.get("input_tokens", 0) or 0
                    k["today_output_tokens"] += r.get("output_tokens", 0) or 0
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
        """Get aggregate statistics for a specific client API key."""
        if self.client_key_repo is None:
            return {}
        key = self.client_key_repo.find_by_id(key_id)
        if not key:
            return {}
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        records, _ = self.log_repo.find_all(
            page=0,
            page_size=5000,
            client_key_name=key["name"],
            start_time=cutoff,
        )
        total_requests = len(records)
        total_input = sum(r.get("input_tokens", 0) or 0 for r in records)
        total_output = sum(r.get("output_tokens", 0) or 0 for r in records)
        success_count = sum(1 for r in records if (r.get("status_code") or 0) < 400)
        error_count = total_requests - success_count
        avg_latency = (
            round(
                sum(r.get("latency_ms", 0) or 0 for r in records) / total_requests
            )
            if total_requests > 0
            else 0
        )
        return {
            "key_name": key["name"],
            "total_requests": total_requests,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "success_count": success_count,
            "error_count": error_count,
            "avg_latency_ms": avg_latency,
        }

    def get_key_docs(self, key_id: int):
        """Generate integration documentation for a client API key."""
        if self.client_key_repo is None:
            return ""
        key = self.client_key_repo.find_by_id(key_id)
        if not key:
            return ""
        status_label = "启用" if key["status"] == "active" else "已禁用"
        key_display = key["key_value"]
        return (
            "# API Key 对接文档 - "
            + key["name"]
            + "\n\n"
            "> **API Key**: `"
            + key_display
            + "`\n"
            "> **状态**: "
            + ("✅ " if key["status"] == "active" else "❌ ")
            + status_label
            + "\n"
            "> **创建时间**: "
            + str(key.get("created_at", ""))
            + "\n\n"
            "## 基础信息\n\n"
            "- **Base URL**: `https://your-domain.com/api/v1`\n"
            "- **认证方式**: Bearer Token\n\n"
            "## 认证方式\n\n"
            "在请求头中携带 API Key 进行认证，两种方式任选其一：\n\n"
            "```http\n"
            "Authorization: Bearer "
            + key_display
            + "\n"
            "```\n\n"
            "或者\n\n"
            "```http\n"
            "X-API-Key: "
            + key_display
            + "\n"
            "```\n\n"
            "## 接口说明\n\n"
            "### 聊天补全 (Chat Completions)\n\n"
            "兼容 OpenAI Chat Completions API 格式。\n\n"
            "```http\n"
            "POST /api/v1/chat/completions\n"
            "Content-Type: application/json\n"
            "Authorization: Bearer "
            + key_display
            + "\n"
            "```\n\n"
            "#### 请求体\n\n"
            "```json\n"
            "{\n"
            '  "model": "alias-name",\n'
            '  "messages": [\n'
            '    { "role": "system", "content": "你是助手" },\n'
            '    { "role": "user", "content": "你好" }\n'
            "  ],\n"
            '  "stream": false\n'
            "}\n"
            "```\n\n"
            "#### 响应示例\n\n"
            "```json\n"
            "{\n"
            '  "id": "chatcmpl-xxx",\n'
            '  "object": "chat.completion",\n'
            '  "choices": [\n'
            "    {\n"
            '      "index": 0,\n'
            '      "message": { "role": "assistant", "content": "你好！" },\n'
            '      "finish_reason": "stop"\n'
            "    }\n"
            "  ],\n"
            '  "usage": {\n'
            '    "prompt_tokens": 10,\n'
            '    "completion_tokens": 20,\n'
            '    "total_tokens": 30\n'
            "  }\n"
            "}\n"
            "```\n\n"
            "## 错误码\n\n"
            "| 状态码 | 说明 |\n"
            "|--------|------|\n"
            "| 401 | API Key 无效或已禁用 |\n"
            "| 429 | 请求频率过高 |\n"
            "| 500 | 内部服务器错误 |\n\n"
            "## 代码示例\n\n"
            "### Python\n\n"
            "```python\n"
            "import openai\n\n"
            "openai.api_key = \""
            + key_display
            + "\"\n"
            'openai.base_url = "https://your-domain.com/api/v1"\n\n'
            "response = openai.chat.completions.create(\n"
            '    model="alias-name",\n'
            '    messages=[{"role": "user", "content": "你好"}]\n'
            ")\n"
            "print(response.choices[0].message.content)\n"
            "```\n\n"
            "### cURL\n\n"
            "```bash\n"
            "curl -X POST https://your-domain.com/api/v1/chat/completions \\\n"
            '  -H "Content-Type: application/json" \\\n'
            '  -H "Authorization: Bearer '
            + key_display
            + '" \\\n'
            '  -d \'{"model": "alias-name", "messages": [{"role": "user", "content": "你好"}]}\'\n'
            "```\n\n"
            "### Node.js\n\n"
            "```javascript\n"
            'import OpenAI from "openai";\n\n'
            "const openai = new OpenAI({\n"
            '  apiKey: "'
            + key_display
            + '",\n'
            '  baseURL: "https://your-domain.com/api/v1"\n'
            "});\n\n"
            "const response = await openai.chat.completions.create({\n"
            '  model: "alias-name",\n'
            '  messages: [{"role": "user", "content": "你好"}]\n'
            "});\n"
            "console.log(response.choices[0].message.content);\n"
            "```\n"
        )

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
        """Get today's input and output token totals for an account+model from logs."""
        from datetime import datetime

        today = datetime.now().strftime("%Y-%m-%d")
        start_of_day = f"{today} 00:00:00"
        end_of_day = f"{today} 23:59:59"

        records, _ = self.log_repo.find_all(
            page=0, page_size=10000,
            account_id=account_id,
            model=model_name,
            start_time=start_of_day,
            end_time=end_of_day,
        )

        total_input = 0
        total_output = 0
        for r in records:
            total_input += r.get("input_tokens", 0) or 0
            total_output += r.get("output_tokens", 0) or 0

        return total_input, total_output

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

        # New aggregated fields for dashboard
        total_input = 0
        total_output = 0
        total_cached = 0
        total_partial_cached = 0
        daily_trend = defaultdict(lambda: {"input": 0, "output": 0, "cached": 0, "total": 0})
        supplier_daily = defaultdict(lambda: defaultdict(int))

        for r in records:
            ts = r.get("timestamp", "")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    heatmap[(dt.weekday(), dt.hour)] += 1
                    date_str = dt.strftime("%Y-%m-%d")
                except (ValueError, TypeError):
                    continue

            input_tok = r.get("input_tokens", 0) or 0
            output_tok = r.get("output_tokens", 0) or 0
            cached_tok = r.get("cached_tokens", 0) or 0
            partial_tok = r.get("prompt_partial_cached", 0) or 0
            tokens = input_tok + output_tok

            total_input += input_tok
            total_output += output_tok
            total_cached += cached_tok
            total_partial_cached += partial_tok

            if r.get("model"):
                model_usage[r["model"]] += tokens
            if ts:
                daily_tokens[date_str][r.get("model", "unknown")] += tokens
                daily_trend[date_str]["input"] += input_tok
                daily_trend[date_str]["output"] += output_tok
                daily_trend[date_str]["cached"] += cached_tok
                daily_trend[date_str]["total"] += tokens

            # Per-supplier daily tracking
            acc_id = r.get("account_id", "unknown")
            if ts and acc_id:
                supplier_daily[acc_id][date_str] += tokens

        # Cache hit rate
        denom = total_cached + total_partial_cached
        cache_hit_rate = round(total_cached / denom * 100, 1) if denom > 0 else 0.0

        # Top models by token usage
        sorted_models = sorted(model_usage.items(), key=lambda x: x[1], reverse=True)
        grand_total = sum(model_usage.values())
        top_models = []
        for model_name, tok_count in sorted_models[:5]:
            top_models.append({
                "model": model_name,
                "tokens": tok_count,
                "pct": round(tok_count / grand_total * 100, 1) if grand_total > 0 else 0,
            })

        return {
            "heatmap": {f"{w},{h}": c for (w, h), c in heatmap.items()},
            "daily_tokens": {d: dict(m) for d, m in daily_tokens.items()},
            "model_usage": dict(model_usage),
            "total_requests": len(records),
            # New dashboard fields
            "total_tokens": total_input + total_output,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "cached_tokens_total": total_cached,
            "partial_cached_total": total_partial_cached,
            "cache_hit_rate": cache_hit_rate,
            "daily_trend": {d: dict(v) for d, v in daily_trend.items()},
            "top_models": top_models,
            "supplier_daily": {k: dict(v) for k, v in supplier_daily.items()},
        }
