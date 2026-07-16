"""Admin API routes for the management panel."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

router = APIRouter()


# ── Request / Response Models ──

class AccountCreate(BaseModel):
    account_id: str = Field(..., description="Unique account identifier")
    api_key: str = Field(..., description="API key")
    base_url: str = Field(..., description="ModelScope base URL")
    region: str = Field("china", description="china or overseas")


class AccountUpdate(BaseModel):
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


class LogQueryParams(BaseModel):
    page: int = 0
    page_size: int = 50
    status_code: Optional[int] = None
    account_id: Optional[str] = None
    model: Optional[str] = None
    is_stream: Optional[bool] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


def get_admin_service():
    """Get AdminService from app state."""
    from main import app
    try:
        return app.state.admin_service
    except AttributeError:
        raise HTTPException(status_code=503, detail="Admin service not initialized")


# ── Accounts ──

@router.get("/accounts")
def list_accounts():
    service = get_admin_service()
    return service.get_accounts()


@router.post("/accounts")
def create_account(body: AccountCreate):
    service = get_admin_service()
    try:
        return service.create_account(
            account_id=body.account_id,
            api_key=body.api_key,
            base_url=body.base_url,
            region=body.region,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"Account {body.account_id} already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/accounts/{account_id}")
def update_account(account_id: int, body: AccountUpdate):
    service = get_admin_service()
    updated = service.update_account(account_id, **body.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Account not found")
    return updated


@router.patch("/accounts/{account_id}/status")
def toggle_account(account_id: int):
    service = get_admin_service()
    toggled = service.toggle_account(account_id)
    if not toggled:
        raise HTTPException(status_code=404, detail="Account not found")
    return toggled


@router.delete("/accounts/{account_id}")
def delete_account(account_id: int):
    service = get_admin_service()
    if not service.delete_account(account_id):
        raise HTTPException(status_code=404, detail="Account not found")
    return {"ok": True}


# ── Mappings ──

@router.get("/mappings")
def list_mappings():
    service = get_admin_service()
    return service.get_mappings()


@router.put("/mappings/bulk")
def bulk_update_mappings(body: MappingBulkUpdate):
    service = get_admin_service()
    service.bulk_update_mappings(body.mappings)
    return service.get_mappings()


@router.delete("/mappings/{alias_name}")
def delete_mapping(alias_name: str):
    service = get_admin_service()
    service.delete_mapping(alias_name)
    return {"ok": True}


# ── Config ──

@router.get("/config")
def get_config():
    service = get_admin_service()
    return service.get_config()


@router.put("/config")
def update_config(body: ConfigBulkUpdate):
    service = get_admin_service()
    service.bulk_set_config(body.config)
    return service.get_config()


# ── Logs ──

@router.get("/logs")
def list_logs(page: int = 0, page_size: int = 50,
              status_code: Optional[int] = None,
              account_id: Optional[str] = None,
              model: Optional[str] = None,
              is_stream: Optional[bool] = None,
              start_time: Optional[str] = None,
              end_time: Optional[str] = None):
    service = get_admin_service()
    records, total = service.get_logs(
        page=page, page_size=page_size,
        status_code=status_code, account_id=account_id,
        model=model, is_stream=is_stream,
        start_time=start_time, end_time=end_time,
    )
    return {"records": records, "total": total, "page": page, "page_size": page_size}


@router.get("/logs/{log_id}")
def get_log_detail(log_id: int):
    service = get_admin_service()
    record = service.get_log_detail(log_id)
    if not record:
        raise HTTPException(status_code=404, detail="Log not found")
    return record


# ── Stats ──

@router.get("/stats")
def get_stats(days: int = 30):
    service = get_admin_service()
    return service.get_stats(days=days)


# ── Alerts ──

@router.get("/alerts")
def list_alerts(days: int = 7):
    """Get alerts from the past N days (derived from logs)."""
    from datetime import datetime, timedelta

    service = get_admin_service()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    records, _ = service.get_logs(start_time=cutoff)

    alerts = []
    for r in records:
        if r.get("status_code") == 429:
            alerts.append({
                "timestamp": r.get("timestamp"),
                "type": "quota_exhausted",
                "level": "warning",
                "account_id": r.get("account_id"),
                "model": r.get("model"),
                "message": f"Account {r.get('account_id')} 的 {r.get('model')} 模型配额耗尽",
            })
        elif r.get("status_code") and r["status_code"] >= 500:
            alerts.append({
                "timestamp": r.get("timestamp"),
                "type": "api_error",
                "level": "error",
                "account_id": r.get("account_id"),
                "model": r.get("model"),
                "message": f"Account {r.get('account_id')} 调用 {r.get('model')} 返回 {r.get('status_code')} 错误",
            })
        elif r.get("status_code") and r["status_code"] >= 400:
            alerts.append({
                "timestamp": r.get("timestamp"),
                "type": "client_error",
                "level": "warning",
                "account_id": r.get("account_id"),
                "model": r.get("model"),
                "message": f"请求失败: {r.get('status_code')} - {r.get('error_message', '')}",
            })

    return alerts
