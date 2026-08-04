"""Admin API routes for the management panel."""
import sys
import time
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import Response
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal

from models.account import DEFAULT_PROVIDER_TYPE

router = APIRouter()

# Track app start time for uptime calculation (set during startup)
APP_START_TIME: Optional[float] = None


# ── Dependency ──────────────────────────────────────────────────────────────

def get_admin_service(request: Request):
    """Resolve AdminService from the *request's* app state.

    This avoids the global-module-``app`` import trap: ``main.app`` and
    ``main.create_app()`` are different objects, so reading the module-
    level ``app.state`` always returned stale / missing data.
    """
    try:
        svc = request.app.state.admin_service
    except AttributeError:
        raise HTTPException(status_code=503, detail="Admin service not initialized")
    if svc is None:
        raise HTTPException(status_code=503, detail="Admin service not initialized")
    return svc


def _refresh_after_account_change(request: Request):
    """Refresh LoadBalancer and clear caches after account mutations.

    Called by admin endpoints that create, update, or delete suppliers.
    Ensures the LoadBalancer picks up new/removed accounts and the
    alias resolver cache is invalidated.
    """
    from api.routes import refresh_load_balancer
    refresh_load_balancer(request)

    # Clear alias resolver cache
    try:
        services = request.app.state.services
        if services and "alias_resolver" in services:
            resolver = services["alias_resolver"]
            if hasattr(resolver, "clear_cache"):
                resolver.clear_cache()
    except Exception:
        pass


# ── Request / Response Models ───────────────────────────────────────────────

class SupplierCreate(BaseModel):
    name: str = Field(..., description="Supplier display name")
    api_key: str = Field(..., description="API key")
    base_url: str = Field(..., description="Provider base URL")
    provider_type: str = Field(default=DEFAULT_PROVIDER_TYPE, description="Provider type: modelscope, sensetime")
    api_keys: List[str] = Field(default_factory=list, description="Additional API keys for rotation")
    api_key_records: List[dict] = Field(default_factory=list, description="API key records with status (id, api_key, status)")


class SupplierUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    status: Optional[str] = None
    provider_type: Optional[str] = None
    api_keys: Optional[List[str]] = None
    api_key_records: Optional[List[dict]] = None


class MappingUpsert(BaseModel):
    alias_name: str
    actual_model_id: str
    description: str = ""
    status: str = "active"


class MappingUpdate(BaseModel):
    description: Optional[str] = None
    status: Optional[str] = None


class MappingRename(BaseModel):
    alias_name: str = Field(..., description="New alias name")


class MappingBulkUpdate(BaseModel):
    mappings: Dict[str, str]


class MappingReorder(BaseModel):
    ordered_ids: List[int] = Field(..., description="Binding IDs in desired order")


class ConfigUpdate(BaseModel):
    key: str
    value: str


class ConfigBulkUpdate(BaseModel):
    config: Dict[str, str]


class SupplierModelCreate(BaseModel):
    model_name: str
    model_type: Literal["text", "image", "code", "voice", "multimodal"] = "text"
    context_length: Optional[int] = None


class SupplierModelBulkUpdate(BaseModel):
    models: List[SupplierModelCreate]


class MappingModelCreate(BaseModel):
    supplier_model_id: int = Field(..., description="supplier_models row id")


class ProviderTypeCreate(BaseModel):
    type_key: str = Field(..., description="Unique provider type key")
    name: str = Field(..., description="Display name")
    description: str = ""
    strategy_type: Literal["header_based", "fixed_window", "fixed_window_per_model"] = "header_based"
    config: Dict[str, Any] = Field(default_factory=dict)
    color: str = "#89b4fa"


class ProviderTypeUpdate(BaseModel):
    type_key: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    strategy_type: Optional[Literal["header_based", "fixed_window", "fixed_window_per_model"]] = None
    config: Optional[Dict[str, Any]] = None
    color: Optional[str] = None


class LogQueryParams(BaseModel):
    page: int = 0
    page_size: int = 50
    status_code: Optional[int] = None
    account_id: Optional[str] = None
    model: Optional[str] = None
    is_stream: Optional[bool] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ── Mappings ───────────────────────────────────────────────────────────────

@router.get("/suppliers")
def list_suppliers(service=Depends(get_admin_service)):
    """Get all suppliers for model selection dropdown."""
    suppliers = service.get_suppliers()
    # Enrich suppliers with their models for dropdown population
    result = []
    for sup in suppliers:
        models = []
        if service.supplier_model_repo:
            models = service.supplier_model_repo.find_by_supplier(sup["id"])
        result.append({
            **sup,
            "models": models
        })
    return result


# ── Supplier Import / Export ───────────────────────────────────────────────
# NOTE: These routes must come BEFORE /suppliers/{supplier_id} to avoid
# FastAPI treating "export"/"import" as a path param.

@router.get("/suppliers/export")
def export_suppliers(format: str = "json", service=Depends(get_admin_service)):
    """Export all suppliers with their models as JSON or YAML file download."""
    data = service.export_suppliers()

    if format == "yaml":
        import yaml
        content = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return Response(
            content=content,
            media_type="application/yaml",
            headers={"Content-Disposition": 'attachment; filename="suppliers_export.yaml"'},
        )

    # Default: JSON
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": 'attachment; filename="suppliers_export.json"'},
    )


@router.get("/config/export")
def export_config(format: str = "json", service=Depends(get_admin_service)):
    """Export full system config: suppliers, provider_types, mappings."""
    data = service.export_config()

    if format == "yaml":
        import yaml
        content = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
        return Response(
            content=content,
            media_type="application/yaml",
            headers={"Content-Disposition": 'attachment; filename="config_export.yaml"'},
        )

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=data,
        headers={"Content-Disposition": 'attachment; filename="config_export.json"'},
    )


@router.post("/suppliers/import")
async def import_suppliers(
    request: Request,
    file: UploadFile = File(..., description="JSON or YAML file with full config data (suppliers, provider_types, mappings)"),
    strategy: str = Form("skip", description="How to handle duplicates: 'skip' or 'overwrite'"),
    service=Depends(get_admin_service),
):
    """Import full system config from an uploaded JSON or YAML file.

    Handles three sections when present in the file: ``provider_types``,
    ``suppliers``, and ``mappings``.  Each section is processed in
    dependency order.
    """
    import yaml

    contents = await file.read()
    raw = contents.decode("utf-8")

    # Auto-detect format from filename or content
    filename = (file.filename or "").lower()
    is_yaml = filename.endswith((".yaml", ".yml"))

    try:
        if is_yaml:
            data = yaml.safe_load(raw)
        else:
            import json
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                # Fallback: try YAML (some JSON is valid YAML)
                data = yaml.safe_load(raw)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"文件解析失败: {str(e)}")

    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="无效的导入格式：根对象必须是字典")

    try:
        result = service.import_suppliers(data, strategy=strategy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"导入失败: {str(e)}")

    _refresh_after_account_change(request)
    return result


@router.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int, service=Depends(get_admin_service)):
    supplier = service.get_supplier(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("/suppliers")
def create_supplier(body: SupplierCreate, request: Request, service=Depends(get_admin_service)):
    try:
        result = service.create_supplier(
            name=body.name,
            api_key=body.api_key,
            base_url=body.base_url,
            provider_type=body.provider_type,
            api_keys=body.api_keys,
            api_key_records=body.api_key_records,
        )
        _refresh_after_account_change(request)
        return result
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"供应商 {body.name} 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, request: Request, body: SupplierUpdate, service=Depends(get_admin_service)):
    updated = service.update_supplier(supplier_id, **body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _refresh_after_account_change(request)
    return updated


@router.patch("/suppliers/{supplier_id}/status")
def toggle_supplier(supplier_id: int, request: Request, service=Depends(get_admin_service)):
    toggled = service.toggle_supplier(supplier_id)
    if not toggled:
        raise HTTPException(status_code=404, detail="Supplier not found")
    _refresh_after_account_change(request)
    return toggled


@router.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, request: Request, service=Depends(get_admin_service)):
    if not service.delete_supplier(supplier_id):
        raise HTTPException(status_code=404, detail="Supplier not found")
    _refresh_after_account_change(request)
    return {"ok": True}


# ── Account API Keys ──────────────────────────────────────────────

class ApiKeyCreate(BaseModel):
    api_key: str = Field(..., description="API key value")


class ApiKeyStatusUpdate(BaseModel):
    status: Literal["active", "frozen"] = Field(..., description="Key status")


@router.get("/suppliers/{supplier_id}/api-keys")
def list_api_keys(supplier_id: int, service=Depends(get_admin_service)):
    """List all API keys for a supplier."""
    return service.get_api_keys(supplier_id)


@router.post("/suppliers/{supplier_id}/api-keys")
def add_api_key(supplier_id: int, body: ApiKeyCreate, request: Request, service=Depends(get_admin_service)):
    """Add an additional API key for a supplier."""
    try:
        return service.add_api_key(supplier_id, body.api_key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/suppliers/{supplier_id}/api-keys/{key_id}/status")
def update_api_key_status(
    supplier_id: int, key_id: int, body: ApiKeyStatusUpdate,
    request: Request, service=Depends(get_admin_service),
):
    """Freeze or unfreeze an API key."""
    try:
        return service.update_api_key_status(key_id, body.status)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/suppliers/{supplier_id}/api-keys/{key_id}")
def delete_api_key(supplier_id: int, key_id: int, request: Request, service=Depends(get_admin_service)):
    """Delete an API key."""
    if not service.delete_api_key(key_id):
        raise HTTPException(status_code=404, detail="API key not found")
    _refresh_after_account_change(request)
    return {"ok": True}


# ── Provider Types ─────────────────────────────────────────────────────────

@router.get("/provider-types")
def list_provider_types(service=Depends(get_admin_service)):
    return service.get_provider_types()


@router.post("/provider-types")
def create_provider_type(body: ProviderTypeCreate, service=Depends(get_admin_service)):
    try:
        return service.create_provider_type(
            type_key=body.type_key, name=body.name, description=body.description,
            strategy_type=body.strategy_type, config=body.config, color=body.color,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"类型标识 {body.type_key} 已存在")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/provider-types/{type_id}")
def update_provider_type(type_id: int, body: ProviderTypeUpdate, service=Depends(get_admin_service)):
    updated = service.update_provider_type(type_id, **body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Provider type not found")
    return updated


@router.delete("/provider-types/{type_id}")
def delete_provider_type(type_id: int, service=Depends(get_admin_service)):
    try:
        if not service.delete_provider_type(type_id):
            raise HTTPException(status_code=404, detail="Provider type not found")
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


# ── Supplier Models ────────────────────────────────────────────────────────

@router.get("/suppliers/{supplier_id}/models")
def list_supplier_models(supplier_id: int, service=Depends(get_admin_service)):
    return service.get_supplier_models(supplier_id)


@router.post("/suppliers/{supplier_id}/models")
def create_supplier_model(
    supplier_id: int, request: Request, body: SupplierModelCreate, service=Depends(get_admin_service)
):
    try:
        result = service.create_supplier_model(
            supplier_id,
            model_name=body.model_name,
            model_type=body.model_type,
            context_length=body.context_length,
        )
        _refresh_after_account_change(request)
        return result
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=409,
                detail=f"Model {body.model_name} already added for this supplier",
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/suppliers/{supplier_id}/models/{model_id}")
def delete_supplier_model(
    supplier_id: int, model_id: int, request: Request, service=Depends(get_admin_service)
):
    if not service.delete_supplier_model(model_id):
        raise HTTPException(status_code=404, detail="Model association not found")
    _refresh_after_account_change(request)
    return {"ok": True}


@router.put("/suppliers/{supplier_id}/models/bulk")
def bulk_set_supplier_models(
    supplier_id: int, body: SupplierModelBulkUpdate, request: Request,
    service=Depends(get_admin_service),
):
    models = [
        {"model_name": m.model_name, "model_type": m.model_type, "context_length": m.context_length}
        for m in body.models
    ]
    result = service.bulk_set_supplier_models(supplier_id, models)
    _refresh_after_account_change(request)
    return result


# ── Mappings ────────────────────────────────────────────────────────────────

@router.get("/mappings")
def list_mappings(service=Depends(get_admin_service)):
    return service.get_mappings()


@router.put("/mappings/bulk")
def bulk_update_mappings(body: MappingBulkUpdate, service=Depends(get_admin_service)):
    service.bulk_update_mappings(body.mappings)
    return service.get_mappings()


@router.patch("/mappings/{alias_name}")
def update_mapping(alias_name: str, body: MappingUpdate, service=Depends(get_admin_service)):
    """Update mapping fields (description, status)."""
    updated = service.update_mapping(alias_name, **body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return updated


@router.put("/mappings/{alias_name}/rename")
def rename_mapping(alias_name: str, body: MappingRename, service=Depends(get_admin_service)):
    """Rename a mapping alias (cascades to mapping_models and model_alias_cache)."""
    try:
        updated = service.rename_mapping(alias_name, body.alias_name)
        if not updated:
            raise HTTPException(status_code=404, detail="Mapping not found")
        return updated
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.patch("/mappings/{alias_name}/status")
def toggle_mapping_status(alias_name: str, service=Depends(get_admin_service)):
    """Toggle mapping status between 'active' and 'disabled'."""
    toggled = service.toggle_mapping_status(alias_name)
    if not toggled:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return toggled


@router.delete("/mappings/{alias_name}")
def delete_mapping(alias_name: str, service=Depends(get_admin_service)):
    service.delete_mapping(alias_name)
    return {"ok": True}


# ── Mapping Models ───────────────────────────────────────────────────────────

@router.get("/mappings/{alias_name}/models")
def list_mapping_models(alias_name: str, service=Depends(get_admin_service)):
    """Get all models bound to a mapping alias (with model_type, context_length)."""
    return service.get_mapping_models(alias_name)


@router.post("/mappings/{alias_name}/models")
def add_mapping_model(
    alias_name: str,
    body: MappingModelCreate,
    service=Depends(get_admin_service)
):
    """Add a model to a mapping alias."""
    try:
        # Determine next sort_order
        existing = service.get_mapping_models(alias_name)
        next_order = len(existing)
        return service.add_mapping_model(
            alias_name,
            supplier_model_id=body.supplier_model_id,
            sort_order=next_order,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"Model already bound to this alias")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/mappings/{alias_name}/models/reorder")
def reorder_mapping_models(
    alias_name: str,
    body: MappingReorder,
    service=Depends(get_admin_service)
):
    """Reorder binding list for an alias. Body: {ordered_ids: [id1, id2, ...]}."""
    try:
        result = service.reorder_mapping_models(alias_name, body.ordered_ids)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/mappings/models/{model_id}")
def remove_mapping_model(model_id: int, service=Depends(get_admin_service)):
    """Remove a model from a mapping alias."""
    if not service.remove_mapping_model(model_id):
        raise HTTPException(status_code=404, detail="Mapping model not found")
    return {"ok": True}


# ── Mapping usage (使用情况) ─────────────────────────────────────────────────

@router.get("/mappings/{alias_name}/logs")
def get_mapping_logs(
    alias_name: str,
    days: int = 7,
    service=Depends(get_admin_service),
):
    """Usage stats for one virtual model (日志 drawer). Operation history removed."""
    return service.get_mapping_usage(alias_name, days=days)


# ── Config ──────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(service=Depends(get_admin_service)):
    return service.get_config()


@router.put("/config")
def update_config(body: ConfigBulkUpdate, service=Depends(get_admin_service)):
    service.bulk_set_config(body.config)
    return service.get_config()


# ── App Info ─────────────────────────────────────────────────────────────────

def _format_uptime(start_time: Optional[float]) -> str:
    if start_time is None:
        return "—"
    delta = time.time() - start_time
    days = int(delta // 86400)
    hours = int((delta % 86400) // 3600)
    mins = int((delta % 3600) // 60)
    return f"{days}d {hours}h {mins}m"


def _get_db_size() -> str:
    """Return human-readable SQLite database file size."""
    try:
        from core.config import ConfigManager
        db_url = ConfigManager.get_database_url()
        db_path = db_url.replace("sqlite:///", "") if db_url.startswith("sqlite:///") else db_url
        size_bytes = Path(db_path).stat().st_size
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 ** 2):.1f} MB"
    except Exception:
        return "—"


@router.get("/info")
def get_app_info(request: Request):
    """Return runtime info: version, uptime, Python, uvicorn, db_size."""
    import importlib.metadata as im

    version = "0.2.0"
    try:
        uvicorn_version = im.version("uvicorn")
    except Exception:
        uvicorn_version = "—"
    return {
        "version": version,
        "uptime": _format_uptime(APP_START_TIME),
        "python": sys.version.split()[0],
        "uvicorn": uvicorn_version,
        "db_size": _get_db_size(),
    }


# ── Logs ────────────────────────────────────────────────────────────────────

@router.get("/logs")
def list_logs(
    page: int = 0,
    page_size: int = 50,
    status_code: Optional[int] = None,
    account_id: Optional[str] = None,
    model: Optional[str] = None,
    is_stream: Optional[bool] = None,
    client_key_name: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    service=Depends(get_admin_service),
):
    records, total = service.get_logs(
        page=page, page_size=page_size,
        status_code=status_code, account_id=account_id,
        model=model, is_stream=is_stream,
        client_key_name=client_key_name,
        start_time=start_time, end_time=end_time,
    )
    return {"records": records, "total": total, "page": page, "page_size": page_size}


@router.get("/logs/{log_id}")
def get_log_detail(log_id: int, service=Depends(get_admin_service)):
    record = service.get_log_detail(log_id)
    if not record:
        raise HTTPException(status_code=404, detail="Log not found")
    return record


# ── Stats ───────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(days: int = 30, service=Depends(get_admin_service)):
    return service.get_stats(days=days)


@router.get("/stats/window")
def get_window_stats(seconds: int = 300, service=Depends(get_admin_service)):
    """Windowed stats for the dashboard live panel. seconds ∈ [60, 2592000] (clamped)."""
    return service.get_window_stats(seconds)


# ── Model Quotas ──────────────────────────────────────────────────────────────

@router.get("/model-quota")
def get_model_quotas(days: int = 0, service=Depends(get_admin_service)):
    """Get model-level quota info aggregated by supplier + model.

    days (default 0 = today) controls the time range used for the
    request success rate and per-range token usage.
    """
    return service.get_model_quotas(days=days)


# ── Alerts ──────────────────────────────────────────────────────────────────

@router.get("/alerts")
def list_alerts(days: int = 7, service=Depends(get_admin_service)):
    """Get alerts from the past N days (derived from logs)."""
    from datetime import timedelta

    from core.timezone import now as _tz_now

    cutoff = (_tz_now() - timedelta(days=days)).isoformat()
    records, _ = service.get_logs(start_time=cutoff, page_size=500)

    alerts = []
    for r in records:
        sc = r.get("status_code")
        display_name = r.get("account_name") or r.get("account_id") or "未知"
        if sc == 429:
            alerts.append({
                "timestamp": r.get("timestamp"),
                "type": "quota_exhausted",
                "level": "warning",
                "account_id": r.get("account_id"),
                "model": r.get("model"),
                "message": f"供应商 {display_name} 的 {r.get('model')} 模型配额耗尽",
            })
        elif sc and sc >= 500:
            alerts.append({
                "timestamp": r.get("timestamp"),
                "type": "api_error",
                "level": "error",
                "account_id": r.get("account_id"),
                "model": r.get("model"),
                "message": f"供应商 {display_name} 调用 {r.get('model')} 返回 {sc} 错误",
            })
        elif sc and sc >= 400:
            alerts.append({
                "timestamp": r.get("timestamp"),
                "type": "client_error",
                "level": "warning",
                "account_id": r.get("account_id"),
                "model": r.get("model"),
                "message": f"请求失败: {sc} - {r.get('error_message', '')}",
            })

    return alerts


# ── Client API Keys ─────────────────────────────────────────────────────────

class ClientKeyCreate(BaseModel):
    name: str = Field(..., description="Client API key name (unique)")
    description: str = Field(default="", description="Optional description")


class ClientKeyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


@router.get("/client-keys")
def list_client_keys(service=Depends(get_admin_service)):
    """Get all client API keys with usage stats."""
    keys = service.get_client_keys()
    # Mask key values for list response
    result = []
    for k in keys:
        kv = k.get("key_value", "")
        masked = kv[:8] + "****" + kv[-8:] if len(kv) > 16 else "****"
        result.append({**k, "key_value_masked": masked})
    return result


@router.post("/client-keys")
def create_client_key(body: ClientKeyCreate, service=Depends(get_admin_service)):
    """Create a new client API key."""
    try:
        key = service.create_client_key(name=body.name, description=body.description)
        return key
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"Key name '{body.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/client-keys/{key_id}")
def update_client_key(key_id: int, body: ClientKeyUpdate, service=Depends(get_admin_service)):
    """Update client API key (name, description, status)."""
    kwargs = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
    updated = service.update_client_key(key_id, **kwargs)
    if not updated:
        raise HTTPException(status_code=404, detail="Client key not found")
    # Mask key value in response
    kv = updated.get("key_value", "")
    masked = kv[:8] + "****" + kv[-8:] if len(kv) > 16 else "****"
    return {**updated, "key_value_masked": masked}


@router.delete("/client-keys/{key_id}")
def delete_client_key(key_id: int, service=Depends(get_admin_service)):
    """Delete a client API key."""
    if not service.delete_client_key(key_id):
        raise HTTPException(status_code=404, detail="Client key not found")
    return {"ok": True}


@router.get("/client-keys/{key_id}/logs")
def get_client_key_logs(
    key_id: int,
    page: int = 0,
    page_size: int = 50,
    days: Optional[int] = None,
    status_code: Optional[int] = None,
    model: Optional[str] = None,
    service=Depends(get_admin_service),
):
    """Get usage logs for a specific client API key."""
    extra = {}
    if days is not None:
        from datetime import timedelta
        from core.timezone import now as _tz_now
        extra["start_time"] = (_tz_now() - timedelta(days=days)).isoformat()
    records, total = service.get_key_usage(
        key_id=key_id,
        page=page,
        page_size=page_size,
        status_code=status_code,
        model=model,
        **extra,
    )
    return {"records": records, "total": total, "page": page, "page_size": page_size}


@router.get("/client-keys/{key_id}/stats")
def get_client_key_stats(key_id: int, days: int = 30, service=Depends(get_admin_service)):
    """Get aggregate statistics for a specific client API key."""
    stats = service.get_key_stats(key_id=key_id, days=days)
    if not stats:
        raise HTTPException(status_code=404, detail="Client key not found")
    return stats


@router.get("/client-keys/{key_id}/docs")
def get_client_key_docs(key_id: int, request: Request, service=Depends(get_admin_service)):
    """Return integration meta-data for a specific client API key (rendered in frontend)."""
    prefix = f"{request.url.scheme}://{request.url.netloc}"
    base_url = prefix + "/api/v1"
    docs = service.get_key_docs(key_id=key_id, base_url=base_url)
    if not docs:
        raise HTTPException(status_code=404, detail="Client key not found")
    return docs


# ── Performance Monitoring ─────────────────────────────────────────────────

@router.get("/performance")
def get_performance_stats(request: Request, service=Depends(get_admin_service)):
    """Get performance statistics for monitoring."""
    try:
        services = request.app.state.services
    except AttributeError:
        services = {}

    stats = {
        "timestamp": time.time(),
        "cache_stats": {}
    }

    if services and "alias_resolver" in services:
        resolver = services["alias_resolver"]
        if hasattr(resolver, "success_cache"):
            stats["cache_stats"]["alias_resolver_success"] = resolver.success_cache.size()
        if hasattr(resolver, "failure_cache"):
            stats["cache_stats"]["alias_resolver_failure"] = resolver.failure_cache.size()

    if services and "load_balancer" in services:
        lb = services["load_balancer"]
        stats["load_balancer"] = {
            "accounts_count": len(lb.accounts) if hasattr(lb, "accounts") else 0
        }

    return stats


@router.get("/circuit-breaker")
def get_circuit_breaker_state(request: Request, service=Depends(get_admin_service)):
    """Get circuit breaker state for all tracked (account, model) pairs.

    Shows which upstream suppliers are currently frozen due to consecutive
    failures, their error type, and remaining freeze time.
    """
    try:
        services = request.app.state.services
    except AttributeError:
        services = {}

    circuit_breaker = services.get("circuit_breaker") if services else None
    if circuit_breaker is None:
        return {"circuits": [], "total": 0}

    states = circuit_breaker.get_all_states()
    return {
        "circuits": states,
        "total": len(states),
        "frozen": sum(1 for s in states if s.get("frozen_remaining", 0) > 0),
        "escalated": sum(1 for s in states if s.get("escalated")),
    }


class CircuitBreakerResetBody(BaseModel):
    """Optional target for a circuit-breaker reset.

    When both ``key_id`` and ``model_name`` are provided, only that circuit
    is cleared (``key_id`` is the ``account_api_keys.id``; 0 = primary key).
    When omitted, every tracked circuit is reset.
    """

    key_id: Optional[int] = None
    model_name: Optional[str] = None


@router.post("/circuit-breaker/reset")
def reset_circuit_breaker(
    request: Request,
    body: Optional[CircuitBreakerResetBody] = None,
    service=Depends(get_admin_service),
):
    """Manually unfreeze circuit breaker state.

    Pass ``key_id`` + ``model_name`` to reset a single circuit, or omit them
    to reset all circuits. Useful for recovering a supplier without restarting.

    ``key_id``: the ``account_api_keys.id`` (0 = primary key from accounts table).
    """
    try:
        services = request.app.state.services
    except AttributeError:
        services = {}

    circuit_breaker = services.get("circuit_breaker") if services else None
    if circuit_breaker is None:
        raise HTTPException(status_code=404, detail="Circuit breaker not available")

    if body and body.key_id is not None and body.model_name:
        cleared = circuit_breaker.clear_one(body.key_id, body.model_name)
        return {"ok": True, "cleared": 1 if cleared else 0, "scope": "one"}

    before = len(circuit_breaker.get_all_states())
    circuit_breaker.clear()
    return {"ok": True, "cleared": before, "scope": "all"}
