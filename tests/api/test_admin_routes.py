"""Tests for admin API routes (management panel backends)."""
import datetime
import pytest
from fastapi.testclient import TestClient

from provider.main import create_app


@pytest.fixture()
def client():
    """TestClient with lifespan triggered so admin service is initialized."""
    app = create_app()
    with TestClient(app) as c:
        yield c


def _tid(suffix: str) -> str:
    """Create a per-run unique name suffix to avoid collisions on the shared DB."""
    now = datetime.datetime.now().strftime("%H%M%S%f")
    return f"adm{now}-{suffix}"


def _list(client):
    return client.get("/api/admin/suppliers").json()


def _create(client, name="test-supplier", api_key="ms-test-key",
            base_url="https://api.modelscope.test/v1"):
    return client.post("/api/admin/suppliers", json={
        "name": name, "api_key": api_key,
        "base_url": base_url,
    }).json()


# ── Suppliers ───────────────────────────────────────────────────────────────

def test_list_suppliers(client):
    data = _list(client)
    assert isinstance(data, list)


def test_create_supplier(client):
    name = _tid("create")
    r = client.post("/api/admin/suppliers", json={
        "name": name, "api_key": "ms-test-key",
        "base_url": "https://api.modelscope.test/v1",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == name
    assert len(body["account_id"]) == 32  # UUID hex
    assert body["status"] == "active"
    assert "id" in body


def test_create_supplier_duplicate_name_returns_409(client):
    name = _tid("dup")
    payload = {
        "name": name, "api_key": "k1", "base_url": "https://u/v1",
    }
    client.post("/api/admin/suppliers", json=payload)
    r = client.post("/api/admin/suppliers", json=payload)
    assert r.status_code == 409


def test_update_supplier(client):
    created = _create(client, _tid("upd"), "k1", "https://u/v1")
    iid = created["id"]
    r = client.put(f"/api/admin/suppliers/{iid}", json={"status": "disabled"})
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"


def test_update_supplier_not_found(client):
    r = client.put("/api/admin/suppliers/99999", json={"status": "active"})
    assert r.status_code == 404


def test_toggle_supplier(client):
    created = _create(client, _tid("toggle"))
    # Fresh supplier is "active"; toggle -> "disabled"
    r = client.patch(f"/api/admin/suppliers/{created['id']}/status")
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"
    # Toggle back -> "active"
    r2 = client.patch(f"/api/admin/suppliers/{created['id']}/status")
    assert r2.status_code == 200
    assert r2.json()["status"] == "active"


def test_toggle_supplier_not_found(client):
    r = client.patch("/api/admin/suppliers/99999/status")
    assert r.status_code == 404


def test_delete_supplier(client):
    before = len(_list(client))
    created = _create(client, _tid("del"), "k3", "https://u/v1")
    r = client.delete(f"/api/admin/suppliers/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert len(_list(client)) == before


def test_delete_supplier_not_found(client):
    r = client.delete("/api/admin/suppliers/99999")
    assert r.status_code == 404


# ── Mappings ────────────────────────────────────────────────────────────────

def test_list_mappings(client):
    data = client.get("/api/admin/mappings").json()
    assert isinstance(data, list)


def test_bulk_update_mappings(client):
    aid = _tid("map")
    payload = {"mappings": {
        aid: "my-actual-model",
    }}
    r = client.put("/api/admin/mappings/bulk", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert any(m["alias_name"] == aid for m in data)


def test_delete_mapping(client):
    aid = _tid("delmap")
    client.put("/api/admin/mappings/bulk", json={
        "mappings": {aid: "some-model"}
    })
    r = client.delete(f"/api/admin/mappings/{aid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


# ── Config ──────────────────────────────────────────────────────────────────

def test_get_config(client):
    data = client.get("/api/admin/config").json()
    assert isinstance(data, dict)
    assert "log_level" in data
    assert "value" in data["log_level"]


def test_update_config(client):
    r = client.put("/api/admin/config", json={"config": {"log_level": "DEBUG"}})
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["log_level"]["value"] == "DEBUG"


# ── Suppliers (detail) ──────────────────────────────────────────────────────

def test_get_supplier(client):
    created = _create(client, _tid("getone"))
    iid = created["id"]
    r = client.get(f"/api/admin/suppliers/{iid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == iid
    assert body["quota_remaining"] == 0
    assert body["quota_limit"] == 0


def test_get_supplier_not_found(client):
    r = client.get("/api/admin/suppliers/99999")
    assert r.status_code == 404


# ── Logs ────────────────────────────────────────────────────────────────────

def test_list_logs_shape(client):
    r = client.get("/api/admin/logs")
    assert r.status_code == 200
    data = r.json()
    for key in ("records", "total", "page", "page_size"):
        assert key in data


def test_list_logs_with_filter_params(client):
    r = client.get("/api/admin/logs?page=0&page_size=10&status_code=429")
    assert r.status_code == 200
    assert "records" in r.json() and "total" in r.json()


def test_get_log_detail_not_found(client):
    r = client.get("/api/admin/logs/99999")
    assert r.status_code == 404


# ── Stats ───────────────────────────────────────────────────────────────────

def test_get_stats(client):
    r = client.get("/api/admin/stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("heatmap", "daily_tokens", "model_usage", "total_requests"):
        assert key in data


def test_get_stats_days_param(client):
    r = client.get("/api/admin/stats?days=7")
    assert r.status_code == 200


# ── Alerts ──────────────────────────────────────────────────────────────────

def test_list_alerts(client):
    r = client.get("/api/admin/alerts")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_list_alerts_days_param(client):
    r = client.get("/api/admin/alerts?days=14")
    assert r.status_code == 200


# ── Mapping usage ──────────────────────────────────────────────────────────

def test_mapping_usage_shape(client):
    aid = _tid("mkguse")
    r = client.put("/api/admin/mappings/bulk", json={"mappings": {aid: "actual-1"}})
    assert r.status_code == 200
    r = client.get(f"/api/admin/mappings/{aid}/logs")
    assert r.status_code == 200
    data = r.json()
    for key in ("alias", "period_days", "usage"):
        assert key in data
    assert data["alias"] == aid
    usage = data["usage"]
    for k in ("requests", "input_tokens", "output_tokens", "cache_tokens",
              "error_count", "cache_hit_rate", "per_model"):
        assert k in usage


def test_mapping_usage_defaults_to_zero(client):
    """An alias that exists but has no requests returns well-formed zeros."""
    aid = _tid("mkguse2")
    client.put("/api/admin/mappings/bulk", json={"mappings": {aid: "actual-1"}})
    r = client.get(f"/api/admin/mappings/{aid}/logs")
    assert r.status_code == 200
    data = r.json()
    assert data["usage"]["requests"] == 0
    assert data["usage"]["input_tokens"] == 0


def test_mapping_usage_days_param(client):
    aid = _tid("mkguse3")
    client.put("/api/admin/mappings/bulk", json={"mappings": {aid: "actual-1"}})
    r = client.get(f"/api/admin/mappings/{aid}/logs?days=30")
    assert r.status_code == 200
    assert r.json()["period_days"] == 30


def test_mapping_usage_attributes_per_actual_model(client):
    """经由虚拟模型路由的请求（model=别名, actual_model_id=底层模型）必须归因到
    per_model 中对应的底层模型行。回归：此前归因误用查询候选 id，导致所有请求
    carrier 都是别名，per_model 各行恒为 0（关联模型用量缺失）。"""
    svc = client.app.state.admin_service
    sup = _create(client, name=_tid("vm-sup"))
    alias = _tid("virtual")
    bound_model = f"real-model-{_tid('m')}"
    # 先建立虚拟模型映射（mapping_models.alias_name 外键指向 model_mappings）
    r = client.put("/api/admin/mappings/bulk", json={"mappings": {alias: bound_model}})
    assert r.status_code == 200
    r = client.post(
        f"/api/admin/mappings/{alias}/models",
        json={"supplier_id": sup["id"], "model_name": bound_model},
    )
    assert r.status_code == 200

    # 记录一条经由虚拟模型路由的请求
    svc.log_request(
        model=alias, actual_model_id=bound_model,
        account_id=sup["account_id"], account_name=sup["name"],
        status_code=200, input_tokens=100, output_tokens=50,
        latency_ms=12, is_stream=False,
        raw_request="{}", raw_response="{}",
    )

    r = client.get(f"/api/admin/mappings/{alias}/logs")
    assert r.status_code == 200
    usage = r.json()["usage"]
    assert usage["requests"] == 1
    assert usage["input_tokens"] == 100
    assert usage["output_tokens"] == 50

    pm = {m["model"]: m for m in usage["per_model"]}
    assert bound_model in pm
    assert pm[bound_model]["requests"] == 1
    assert pm[bound_model]["input_tokens"] == 100
    assert pm[bound_model]["output_tokens"] == 50
    assert pm[bound_model]["supplier"] == sup["name"]


# ── Provider Types ─────────────────────────────────────────────────────────

def test_list_provider_types_includes_builtins(client):
    r = client.get("/api/admin/provider-types")
    assert r.status_code == 200
    keys = {pt["type_key"] for pt in r.json()}
    assert {"modelscope", "sensetime"} <= keys
    by_key = {pt["type_key"]: pt for pt in r.json()}
    # config 应解析为 dict
    assert isinstance(by_key["sensetime"]["config"], dict)
    assert by_key["sensetime"]["config"].get("max_requests") == 1500


def test_provider_type_crud(client):
    key = _tid("ptype")
    # create
    r = client.post("/api/admin/provider-types", json={
        "type_key": key, "name": "自定义", "strategy_type": "fixed_window",
        "config": {"window_seconds": 3600, "max_requests": 100}, "color": "#a6e3a1",
    })
    assert r.status_code == 200
    created = r.json()
    assert created["type_key"] == key
    assert created["config"]["max_requests"] == 100
    pid = created["id"]

    # update
    r = client.put(f"/api/admin/provider-types/{pid}",
                   json={"name": "自定义-改", "config": {"window_seconds": 7200, "max_requests": 200}})
    assert r.status_code == 200
    assert r.json()["name"] == "自定义-改"
    assert r.json()["config"]["max_requests"] == 200

    # delete custom type
    r = client.delete(f"/api/admin/provider-types/{pid}")
    assert r.status_code == 200


def test_delete_builtin_provider_type_blocked(client):
    pts = client.get("/api/admin/provider-types").json()
    builtin = next(p for p in pts if p["type_key"] == "modelscope")
    r = client.delete(f"/api/admin/provider-types/{builtin['id']}")
    assert r.status_code == 409


def test_create_provider_type_duplicate_409(client):
    r = client.post("/api/admin/provider-types",
                    json={"type_key": "modelscope", "name": "dup"})
    assert r.status_code == 409


def test_create_provider_type_per_model_strategy(client):
    """Should create and update a provider type with fixed_window_per_model strategy."""
    key = _tid("ptper")
    # create with per-model config
    r = client.post("/api/admin/provider-types", json={
        "type_key": key, "name": "自定义按模型",
        "strategy_type": "fixed_window_per_model",
        "config": {
            "window_seconds": 18000,
            "max_requests": 1500,
            "models": {
                "model-a": {"window_seconds": 18000, "max_requests": 3000},
                "model-b": {"max_requests": 500},
            },
        },
        "color": "#f38ba8",
    })
    assert r.status_code == 200
    created = r.json()
    assert created["strategy_type"] == "fixed_window_per_model"
    assert created["config"]["models"]["model-a"]["max_requests"] == 3000
    pid = created["id"]

    # update
    r = client.put(f"/api/admin/provider-types/{pid}", json={
        "config": {
            "window_seconds": 3600,
            "max_requests": 500,
            "models": {"model-c": {"max_requests": 100}},
        },
    })
    assert r.status_code == 200
    assert r.json()["config"]["models"]["model-c"]["max_requests"] == 100

    # delete
    r = client.delete(f"/api/admin/provider-types/{pid}")
    assert r.status_code == 200
