"""Admin API routes for the management panel."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal

router = APIRouter()


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


# ── Request / Response Models ───────────────────────────────────────────────

class AccountCreate(BaseModel):
    name: str = Field(..., description="Supplier display name")
    api_key: str = Field(..., description="API key")
    base_url: str = Field(..., description="ModelScope base URL")
    region: str = Field("china", description="china or overseas")


class AccountUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    region: Optional[str] = None
    status: Optional[str] = None


class MappingUpsert(BaseModel):
    alias_name: str
    region: str
    actual_model_id: str


class MappingBulkUpdate(BaseModel):
    mappings: Dict[str, Dict[str, str]]


class ConfigUpdate(BaseModel):
    key: str
    value: str


class ConfigBulkUpdate(BaseModel):
    config: Dict[str, str]


class SupplierModelCreate(BaseModel):
    model_name: str
    model_type: Literal["text", "image", "code", "voice"] = "text"
    context_length: Optional[int] = None


class SupplierModelBulkUpdate(BaseModel):
    models: List[SupplierModelCreate]


class LogQueryParams(BaseModel):
    page: int = 0
    page_size: int = 50
    status_code: Optional[int] = None
    account_id: Optional[str] = None
    model: Optional[str] = None
    is_stream: Optional[bool] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


# ── Suppliers ───────────────────────────────────────────────────────────────

@router.get("/suppliers")
def list_suppliers(service=Depends(get_admin_service)):
    return service.get_accounts()


@router.get("/suppliers/{supplier_id}")
def get_supplier(supplier_id: int, service=Depends(get_admin_service)):
    supplier = service.get_account(supplier_id)
    if not supplier:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return supplier


@router.post("/suppliers")
def create_supplier(body: AccountCreate, service=Depends(get_admin_service)):
    try:
        return service.create_account(
            name=body.name,
            api_key=body.api_key,
            base_url=body.base_url,
            region=body.region,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"Supplier {body.name} already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/suppliers/{supplier_id}")
def update_supplier(supplier_id: int, body: AccountUpdate, service=Depends(get_admin_service)):
    updated = service.update_account(supplier_id, **body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return updated


@router.patch("/suppliers/{supplier_id}/status")
def toggle_supplier(supplier_id: int, service=Depends(get_admin_service)):
    toggled = service.toggle_account(supplier_id)
    if not toggled:
        raise HTTPException(status_code=404, detail="Supplier not found")
    return toggled


@router.delete("/suppliers/{supplier_id}")
def delete_supplier(supplier_id: int, service=Depends(get_admin_service)):
    if not service.delete_account(supplier_id):
        raise HTTPException(status_code=404, detail="Supplier not found")
    return {"ok": True}


# ── Supplier Models ────────────────────────────────────────────────────────

@router.get("/suppliers/{supplier_id}/models")
def list_supplier_models(supplier_id: int, service=Depends(get_admin_service)):
    return service.get_supplier_models(supplier_id)


@router.post("/suppliers/{supplier_id}/models")
def create_supplier_model(
    supplier_id: int, body: SupplierModelCreate, service=Depends(get_admin_service)
):
    try:
        return service.create_supplier_model(
            supplier_id,
            model_name=body.model_name,
            model_type=body.model_type,
            context_length=body.context_length,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(
                status_code=409,
                detail=f"Model {body.model_name} already added for this supplier",
            )
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/suppliers/{supplier_id}/models/{model_id}")
def delete_supplier_model(
    supplier_id: int, model_id: int, service=Depends(get_admin_service)
):
    if not service.delete_supplier_model(model_id):
        raise HTTPException(status_code=404, detail="Model association not found")
    return {"ok": True}


@router.put("/suppliers/{supplier_id}/models/bulk")
def bulk_set_supplier_models(
    supplier_id: int, body: SupplierModelBulkUpdate, service=Depends(get_admin_service)
):
    models = [
        {"model_name": m.model_name, "model_type": m.model_type, "context_length": m.context_length}
        for m in body.models
    ]
    return service.bulk_set_supplier_models(supplier_id, models)


# ── Mappings ────────────────────────────────────────────────────────────────

@router.get("/mappings")
def list_mappings(service=Depends(get_admin_service)):
    return service.get_mappings()


@router.put("/mappings/bulk")
def bulk_update_mappings(body: MappingBulkUpdate, service=Depends(get_admin_service)):
    service.bulk_update_mappings(body.mappings)
    return service.get_mappings()


@router.delete("/mappings/{alias_name}")
def delete_mapping(alias_name: str, service=Depends(get_admin_service)):
    service.delete_mapping(alias_name)
    return {"ok": True}


# ── Config ──────────────────────────────────────────────────────────────────

@router.get("/config")
def get_config(service=Depends(get_admin_service)):
    return service.get_config()


@router.put("/config")
def update_config(body: ConfigBulkUpdate, service=Depends(get_admin_service)):
    service.bulk_set_config(body.config)
    return service.get_config()


# ── Logs ────────────────────────────────────────────────────────────────────

@router.get("/logs")
def list_logs(
    page: int = 0,
    page_size: int = 50,
    status_code: Optional[int] = None,
    account_id: Optional[str] = None,
    model: Optional[str] = None,
    is_stream: Optional[bool] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    service=Depends(get_admin_service),
):
    records, total = service.get_logs(
        page=page, page_size=page_size,
        status_code=status_code, account_id=account_id,
        model=model, is_stream=is_stream,
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


# ── Alerts ──────────────────────────────────────────────────────────────────

@router.get("/alerts")
def list_alerts(days: int = 7, service=Depends(get_admin_service)):
    """Get alerts from the past N days (derived from logs)."""
    from datetime import datetime, timedelta

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    records, _ = service.get_logs(start_time=cutoff)

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
