# 虚拟模型系统设计

> **日期:** 2026-07-19
> **项目:** ModelScope Proxy — 后端路由 & 前端映射页
> **状态:** Draft / 待用户审阅

---

## 1. 目标

将「模型映射」页面重新定位为「虚拟模型」，使一个虚拟模型ID（alias）可以绑定多个供应商的不同模型。当 AI 工具通过该虚拟模型ID 请求时，服务在绑定的模型列表中使用全局配置的负载均衡策略进行请求分发。

---

## 2. 需求

| # | 需求 | 说明 |
|---|------|------|
| R1 | **虚拟模型概念** | 页面标题从「模型映射」改为「虚拟模型」，字段「别名」改为「虚拟模型ID」 |
| R2 | **绑定多个供应商模型** | 一个虚拟模型ID 可绑定多个（供应商 + 模型名）条目 |
| R3 | **绑定模型路由** | 请求时若虚拟模型有绑定，则只在绑定条目中按全局策略选一个 |
| R4 | **fallback 兼容** | 无绑定的虚拟模型 fallback 到旧逻辑（actual_model_id → alias_resolver） |
| R5 | **隐藏 actual_model_id** | UI 不再展示/编辑 actual_model_id，但保留数据用于 fallback |
| R6 | **内联绑定编辑** | 添加/编辑虚拟模型时，绑定模型区域直接内联在主表单中 |
| R7 | **列表展开详情** | 卡片显示绑定数量，点击展开列出具体条目（供应商+模型名），支持直接删除 |
| R8 | **全局策略生效** | load_balancer_strategy 配置被实际读取，round_robin/least_conn/random 三种策略在绑定条目间生效 |

---

## 3. 架构概览

### 3.1 请求流（改造后）

```
AI 工具 ──POST /v1/chat/completions {model: "my-alias"}──► routes.py
                              │
                              ▼
                    ┌─────────────────┐
                     │  AliasRouter    │
                    │  .route(model)  │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ 有绑定？                      │ 无绑定
              ▼                              ▼
    按全局策略选一条目                  ┌──────────────────┐
    → (account, model_name)            │ 旧流程：          │
    → 直接转发（model=model_name）     │ 全局 LB 选账号    │
                                       │ + alias_resolver │
                                       │ 解析 actual_id   │
                                       └──────────────────┘
```

### 3.2 新增组件：AliasRouter

```
┌──────────────────────────────────────────────────────┐
│  AliasRouter                                          │
│  ┌────────────────────────────────────────────────┐  │
│  │  mapping_model_repo  → 查绑定条目              │  │
│  │  account_repo        → 解析供应商凭证          │  │
│  │  strategy            → 从 config 实时读取      │  │
│  └────────────────────────────────────────────────┘  │
│                                                      │
│  route(alias) → RoutingResult(account, model_name)   │
│                → None（无绑定时）                     │
└──────────────────────────────────────────────────────┘
```

### 3.3 数据流（绑定路由）

```
mapping_models 表                  accounts 表
┌────────────────────┐           ┌──────────────────┐
│ alias_name: my-alias│           │ id: 1            │
│ supplier_id: 1      │──────────►│ api_key: xxx     │
│ model_name: qwen-72b│           │ base_url: yyy   │
├────────────────────┤           └──────────────────┘
│ alias_name: my-alias│
│ supplier_id: 2      │──────────► accounts.id = 2
│ model_name: gpt-4o  │
└────────────────────┘
```

---

## 4. 后端设计

### 4.1 AliasRouter 服务

新建 `services/alias_router.py`：

```python
from dataclasses import dataclass, field
from typing import Optional
import random
import logging

logger = logging.getLogger(__name__)


@dataclass
class RoutingResult:
    """路由结果：选中的账户 + 实际模型名。"""
    account: object       # ModelScopeAccount 实例
    model_name: str       # 直接发给下游的模型名


class AliasRouter:
    """根据虚拟模型ID的绑定条目选择路由。

    职责：
    1. 查找 alias 在 mapping_models 表中的所有绑定条目
    2. 有绑定时按策略选一个，返回 (account, model_name)
    3. 无绑定时返回 None（调用方 fallback 到旧逻辑）
    """

    def __init__(self, mapping_model_repo, account_repo, config_repo):
        self.mapping_model_repo = mapping_model_repo
        self.account_repo = account_repo
        self.config_repo = config_repo
        # least_conn 策略的每条目请求计数
        self._connection_counts = {}

    def _get_strategy(self) -> str:
        """从 system_config 实时读取策略，默认 round_robin。"""
        val = self.config_repo.get("load_balancer_strategy")
        return val if val in ("round_robin", "least_conn", "random") else "round_robin"

    def route(self, alias: str) -> Optional[RoutingResult]:
        """为 alias 选择一个绑定条目。

        Returns:
            RoutingResult（有绑定时）或 None（无绑定时）
        """
        entries = self.mapping_model_repo.find_by_alias(alias)
        if not entries:
            return None

        # 解析每个条目对应的 account
        candidates = []
        for entry in entries:
            account = self.account_repo.find_by_id(entry["supplier_id"])
            if account:
                candidates.append((account, entry["model_name"]))

        if not candidates:
            logger.warning(f"Alias '{alias}' has bindings but no valid accounts found")
            return None

        strategy = self._get_strategy()

        if strategy == "round_robin":
            idx = self._round_robin_index(alias, len(candidates))
            selected = candidates[idx]
        elif strategy == "random":
            selected = random.choice(candidates)
        elif strategy == "least_conn":
            selected = self._least_conn(alias, candidates)

        account_dict, model_name = selected
        # 转换为 ModelScopeAccount
        from models.account import ModelScopeAccount
        ms_account = ModelScopeAccount(
            account_id=account_dict["account_id"],
            name=account_dict.get("name", ""),
            api_key=account_dict["api_key"],
            base_url=account_dict["base_url"],
        )
        logger.info(
            f"AliasRouter: routed '{alias}' → account={ms_account.account_id}, "
            f"model={model_name}, strategy={strategy}"
        )
        return RoutingResult(account=ms_account, model_name=model_name)

    def _round_robin_index(self, alias: str, size: int) -> int:
        """rr 计数器按 alias 隔离。"""
        key = f"alias_router_rr"
        # 用类变量持有，保持与 LB 类似的简单 round-robin
        if not hasattr(self, "_rr_counters"):
            self._rr_counters = {}
        current = self._rr_counters.get(alias, 0)
        self._rr_counters[alias] = (current + 1) % size
        return current

    def _least_conn(self, alias, candidates):
        """least_conn 策略：选择当前连接数最少的候选。"""
        if alias not in self._connection_counts:
            self._connection_counts = {alias: [0] * len(c)}
        counts = self._connection_counts[alias]
        # 更新 counts 长度（候选数可能变化）
        while len(counts) < len(candidates):
            counts.append(0)
        min_idx = counts.index(min(counts[:len(candidates)]))
        counts[min_idx] += 1
        return candidates[min_idx]
```

**设计要点：**
- `config_repo.get()` 在每次 `route()` 时实时读取策略，切换后立即生效
- `round_robin` 计数器按 alias 隔离（同一个虚拟模型的请求轮转）
- `least_conn` 用简单内存计数，进程重启归零（可接受，与现有 LB 一致）
- 无绑定条目或绑定条目都找不到有效账号 → 返回 None，不抛异常

### 4.2 请求流改造（routes.py）

```python
@router.post("/v1/chat/completions")
async def chat_completions(request, fastapi_request, services=Depends(get_services)):
    # ... 认证 ...

    alias_router = fastapi_request.app.state.alias_router
    load_balancer = services["load_balancer"]
    alias_resolver = services["alias_resolver"]
    # ...

    # 1. 尝试绑定路由
    route_result = alias_router.route(request.model)

    if route_result is not None:
        # 2a. 有绑定 → 直接用路由结果
        selected_account = route_result.account
        model_name = route_result.model_name
        request_body = {**base_body, "model": model_name}
        # 转发请求（与现有逻辑相同，仅 model 和 account 来源不同）
    else:
        # 2b. 无绑定 → 旧流程
        selected_account = load_balancer.select_account(request.model)
        actual_model_id = await alias_resolver.resolve_alias(selected_account, request.model)
        request_body = {**base_body, "model": actual_model_id}
```

**要点：**
- 绑定路由是旧流程的前置分支，不改变旧流程的任何行为
- logging 使用 route_result.account 而非 selected_account，保持日志语义

### 4.3 依赖注入（main.py / service_init.py）

在 `initialize_all()` 或 `lifespan` 中构建 AliasRouter 并挂载到 `app.state.alias_router`。

最好挂载在 `ServiceInitializer.initialize_all()` 里，与 LB 同级：

```python
# service_init.py
from services.alias_router import AliasRouter

alias_router = AliasRouter(
    mapping_model_repo=mapping_model_repo,
    account_repo=AccountRepository(database),  # 需要新建或在 initialize_all 复用
    config_repo=ConfigRepository(database),
)

services["alias_router"] = alias_router
```

`AccountRepository` 已在 project 中，只需在 `initialize_all` 中实例化。

---

## 5. 前端设计

### 5.1 Mappings.vue → 改名/重定位

- **不重命名文件**（避免路由/侧边栏连锁改动）
- 页面 header title 改为「虚拟模型」
- subtitle: "管理虚拟模型ID及其绑定的供应商模型"
- 按钮文案「添加映射」→「添加虚拟模型」，「编辑映射」→「编辑虚拟模型」

### 5.2 表单（添加/编辑抽屉）

改造前（现有）：
```
[别名 input] [实际模型ID input] → [管理绑定模型] 按钮 → 打开第二个抽屉
```

改造后（新）：
```
[虚拟模型ID input]
──────────────────────────────
绑定模型
  供应商 dropdown → 模型 dropdown → [添加] 按钮
  ┌──────────────────────────────────────────┐
  │ 供应商A / qwen-72b              [×]      │
  │ 供应商B / gpt-4o                [×]      │
  └──────────────────────────────────────────┘
  （空态）暂无绑定模型，请求时将直接使用虚拟模型ID
──────────────────────────────
                    [取消]  [保存]
```

**关键改动：**
- 删除 `actual_model_id` 字段（完全隐藏）
- 删除「管理绑定模型」按钮和第二个 Drawer
- 绑定区域内联在主表单底部
- 字段 `alias_name` → 前端展示为「虚拟模型ID」

### 5.3 列表/卡片展示

**数量展示：**
```
[虚拟模型ID: my-alias]  ▸ 绑定 3 个模型 ▼
```

**展开后：**
```
[虚拟模型ID: my-alias]  ▸ 绑定 3 个模型 ▲
  • 供应商A / qwen-72b     [删除]
  • 供应商B / gpt-4o       [删除]
  • 供应商C / deepseek-v3  [删除]
```

三种视图（row / grid / table）均支持该展开交互。

### 5.4 MappingModelSelector 改造

组件定位从"抽屉内的选择器"改为"可内联复用的绑定编辑区域"：

- 移除 Drawer 依赖（目前也没有，它本身只是一个 div）
- 维持现有的供应商→模型→添加→列表逻辑
- 增加 `supplier_name` 显示（依赖 `/api/suppliers` 返回的 name）

或者直接将其模板内联进 Mappings.vue 的抽屉里（更直接，减少 props/emit 传递的复杂度）。

**推荐：内联进 Mappings.vue**
- 当前 MappingModelSelector 通过 `v-model` + emit 传递 `bound_models`，但它在抽屉里时和外部表单状态同步有问题（用 `Date.now()` 作为临时 id、新增绑定时用 `'current-alias'` 占位符调后端 API）
- 内联后 `bound_models` 直接是 Mappings.vue 的 ref，删除/添加直接操作，虚拟模型ID 已知（来自表单），无需占位符

---

## 6. 数据迁移

### 6.1 数据库

**无新表、无列改动。** `mapping_models` 表已存在且结构满足需求：
```sql
mapping_models(id, alias_name, supplier_id, model_name, created_at, updated_at)
```

### 6.2 actual_model_id 处理

| 策略 | 处理 |
|------|------|
| 保留现有数据 | UI 不再编辑，但旧数据继续存在 |
| 旧流程 fallback | 无绑定时 alias_resolver 仍读 model_mappings.actual_model_id → 行为不变 |

### 6.3 API 兼容

- `PUT /mappings/bulk` 仍接受 `{alias: actual_model_id}` 格式
- 但前端不再调用 actual_model_id 字段（新增映射时只传 alias_name，actual_model_id 留空或用 alias 自身）
- **后端需兼容** actual_model_id 为空的情况：若 `bulk_update_mappings` 的 value 为空，设为 alias_name 自身

---

## 7. 改造文件清单

### 7.1 新建文件

| 文件 | 说明 |
|------|------|
| `services/alias_router.py` | AliasRouter 服务（含 RoutingResult） |

### 7.2 后端修改文件

| 文件 | 改动 |
|------|------|
| `api/routes.py` | `/chat/completions` 先调 alias_router，无结果走旧流程 |
| `core/service_init.py` | 构建 AliasRouter 并挂载到 services |
| `main.py` | lifespan 中挂载 alias_router 到 app.state |
| `repositories/mapping_repository.py` | `bulk_upsert` 兼容 value 为空时设为 alias |
| `services/admin_service.py` | cleanup：删除 `resolve_mapping_alias` 的旧代码（已由 AliasRouter 替代） |

### 7.3 前端修改文件

| 文件 | 改动 |
|------|------|
| `web/src/pages/Mappings.vue` | 标题/字段重命名；内联绑定区域；列表展开详情；移除 actual_model_id 字段 |
| `web/src/components/MappingModelSelector.vue` | 可内联复用（或直接内联进 Mappings.vue） |

### 7.4 无需修改的文件

- `models/alias_resolver.py` — 继续作为 fallback 路径
- `services/load_balancer.py` — 无绑定时仍走此路径
- `repositories/mapping_model_repository.py` — 表结构和查询满足需求
- `repositories/account_repository.py` — find_by_id 已有

---

## 8. 用户故事

1. **创建虚拟模型**：用户点击「添加虚拟模型」→ 输入虚拟模型ID（如 `my-chat-model`）→ 直接添加绑定条目（供应商A/qwen-72b、供应商B/gpt-4o）→ 保存
2. **AI 工具请求**：AI 工具用 `model: "my-chat-model"` 请求 → 服务看到绑定了 2 个模型 → 按全局策略（如 round_robin）选一个 → 用该供应商凭证转发，model 字段用绑定的 model_name
3. **无绑定虚拟模型**：用户只创建了虚拟模型ID，没加绑定 → fallback 到旧逻辑，和以前行为一致
4. **展开查看详情**：用户在列表看到「绑定 3 个模型」→ 点击展开 → 看到具体供应商和模型名 → 可直接删除某条绑定
5. **编辑虚拟模型**：点击编辑 → 主表单底部直接显示绑定列表 → 可增删条目 → 保存

---

## 9. 向后兼容

- 现有映射数据无绑定 → 继续走旧流程，行为不变
- 现有映射数据有绑定 → 自动切到新路由，无需迁移
- 现有通过 `PUT /mappings/bulk` 传 actual_model_id 的调用方仍可用
- `alias_resolver` 和 `load_balancer` 保留，作为 fallback 路径

---

## 10. 未覆盖范围（明确不做）

- 不修改 `mapping_models` 表结构
- 不新增数据库迁移脚本
- 不改动 `load_balancer_strategy` 配置的 UI（Config.vue 已有）
- 不实现绑定级别的独立策略（始终用全局策略）
- 不删除 `actual_model_id` 列（保留数据）
- 不重命名 Mappings.vue 文件（只改展示名，避免路由连锁改动）
