# 供应商模型管理 — 设计文档

> 日期：2026-07-17
> 状态：待审核

## 1. 背景与问题

当前系统中"供应商"（accounts）和"模型映射"（model_mappings）是两套完全独立的机制：

- **供应商**（`accounts` 表）只记录账户凭据（api_key、base_url、region），不包含任何模型信息。
- **模型映射**（`model_mappings` 表）是全局级别的别名→实际模型 ID 映射，与供应商无关。
- **负载均衡器**（LoadBalancer）从所有活跃供应商中做 round-robin 选择，不校验该供应商是否支持请求的模型。

**问题**：一个供应商可能只支持部分模型，但当前系统会把所有请求路由到任意供应商，导致请求到不支持的模型时报错。

**目标**：在供应商层面管理该供应商支持的模型列表，让负载均衡器只从"支持该模型"的活跃供应商中做选择。模型信息的管理入口完全合并到供应商添加/编辑页面。

## 2. 请求路由链路（最终设计）

```
用户请求: model=alias_x
    │
    ▼
① AliasResolver
   用 model_mappings 表把 alias_x → actual_model_name（如 qwen-max）
    │
    ▼
② LoadBalancer
   查 supplier_models 表，找出 region 匹配 + 支持 actual_model_name 的活跃供应商列表
   从该列表中按策略（round-robin）选一个
    │
    ▼
③ HttpClient
   向选中的供应商的 base_url 发送请求
```

- **model_mappings 表保持不变**，继续用于别名→实际模型名的解析。
- **supplier_models 表**是新引入的供应商×模型关联表。

## 3. 数据库设计

### 3.1 新增表：supplier_models

```sql
CREATE TABLE supplier_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    model_name TEXT NOT NULL,
    model_type TEXT NOT NULL,              -- 模型能力类型: text / image / code / voice
    context_length INTEGER,                -- 上下文长度（token 数），可为 NULL
    UNIQUE(supplier_id, model_name)
);

CREATE INDEX idx_supplier_models_name ON supplier_models(model_name);
CREATE INDEX idx_supplier_models_supplier ON supplier_models(supplier_id);
```

**字段说明**：

| 字段 | 含义 |
|------|------|
| `supplier_id` | 关联的供应商 accounts.id，供应商删除时级联删除 |
| `model_name` | 该供应商支持的实际模型名（如 qwen-max、glm-4） |
| `model_type` | 模型能力分类：`text`（文本）、`image`（图像）、`code`（代码）、`voice`（语音） |
| `context_length` | 上下文长度（token 数），可为 NULL。用于展示和路由决策参考 |

**约束**：同一供应商下 `model_name` 唯一（同一模型不重复添加）。

## 4. 后端设计

### 4.1 新增 Repository：SupplierModelRepository

**文件**：`repositories/supplier_model_repository.py`

```python
class SupplierModelRepository:
    def find_by_supplier(self, supplier_id: int) -> List[dict]:
    def create(self, supplier_id, model_name, model_type, context_length) -> dict:
    def delete(self, model_id: int) -> bool:
    def bulk_upsert(self, supplier_id, models: List[dict]):
    def delete_by_supplier(self, supplier_id) -> int:  # 供应商删除时清理
    def find_suppliers_for_model(self, model_name) -> List[dict]:
```

`find_suppliers_for_model` 是关键查询，JOIN accounts 表，只返回 status='active' 的供应商及其完整信息（用于 LoadBalancer 筛选）。

### 4.2 新增 AdminService 方法

**文件**：`services/admin_service.py`

- `get_supplier_models(supplier_id)` → 列表
- `create_supplier_model(supplier_id, model_name, model_type, context_length)`
- `delete_supplier_model(model_id)`
- `bulk_set_supplier_models(supplier_id, models)`
- 修改 `delete_account(supplier_id)`：删除前先 `delete_by_supplier`

### 4.3 新增 API 端点

**文件**：`api/admin_routes.py`

```
GET  /suppliers/{supplier_id}/models          # 获取供应商支持的模型列表
POST /suppliers/{supplier_id}/models          # 添加模型（body: {model_name, model_type, region}）
DELETE /suppliers/{supplier_id}/models/{id}   # 删除单条模型关联
PUT  /suppliers/{supplier_id}/models/bulk     # 批量替换（用于添加/编辑表单一次性提交）
```

**Pydantic model**：
```python
class SupplierModelCreate(BaseModel):
    model_name: str
    model_type: str  # text/image/code/voice
    context_length: Optional[int] = None

class SupplierModelBulkUpdate(BaseModel):
    models: List[SupplierModelCreate]
```

**删除供应商时**：利用 `ON DELETE CASCADE` 自动清理，后端无需额外处理。

### 4.4 修改 LoadBalancer

**文件**：`services/load_balancer.py`

当前 `select_account(model_name)` 只过滤 `unavailable_models`，不校验供应商是否声明支持该模型。改为：

1. 接收 `model_name` 参数。
2. 通过 `SupplierModelRepository.find_suppliers_for_model(model_name)` 获取候选供应商列表。
3. 叠加现有 `unavailable_models` 过滤。
4. 若候选为空，fallback 到所有活跃供应商（向后兼容），记录 warning 日志。
5. 从候选中按 round-robin 选一个。

**LoadBalancer 初始化时**需要注入 `SupplierModelRepository` 实例。

**ServiceInitializer 改动**（`core/service_init.py`）：
- 初始化 `SupplierModelRepository`
- 传入 `LoadBalancer`

### 4.5 修改 AliasResolver

**文件**：`models/alias_resolver.py`

AliasResolver 现有逻辑是 `resolve_alias(account, alias)` 返回实际模型 ID。当前返回的是 alias 本身（因为 model_mappings 没有真正参与解析）。

**改动**：让 AliasResolver 初始化时接收 `MappingRepository`，真正从 `model_mappings` 表查询别名→模型名的映射。解析逻辑：

1. 查 `model_mappings`，用 `alias_name=alias` 找 `actual_model_id`。
2. 若找到则返回 actual_model_id；若未找到则 fallback 返回 alias 本身（向后兼容）。
3. 可选：缓存解析结果（已有 `model_alias_cache` 表，但暂不使用，留作后续优化）。

**注意**：去掉 region 条件后，别名解析不再区分区域，直接按别名全局查找。

### 4.6 修改 chat/completions 路由

**文件**：`api/routes.py`

当前 `load_balancer.select_account(request.model)` 只传模型名。改为：

1. `alias_resolver.resolve_alias(alias)` → actual_model_name
2. `load_balancer.select_account(actual_model_name)` → 选中的供应商

LoadBalancer 现在会基于 `supplier_models` 表筛选支持该模型的活跃供应商。

## 5. 前端设计

### 5.1 API 层

**文件**：`web/src/api/index.js`

```javascript
export const getSupplierModels = (id) => api.get(`/suppliers/${id}/models`)
export const bulkSetSupplierModels = (id, data) => api.put(`/suppliers/${id}/models/bulk`, data)
export const createSupplierModel = (id, data) => api.post(`/suppliers/${id}/models`, data)
export const deleteSupplierModel = (id, modelId) => api.delete(`/suppliers/${id}/models/${modelId}`)
```

### 5.2 添加供应商抽屉

**文件**：`web/src/pages/Accounts.vue`

添加表单在现有字段（name、api_key、base_url、region）下方新增「支持模型」区域：

```
┌─ 支持模型 ────────────────────────────┐
│  ┌────────────┬────────┬──────────┐   │
│  │ 模型名称    │ 类型   │ 上下文长度 │ ✕ │
│  ├────────────┼────────┼──────────┤   │
│  │ qwen-max   │ [文本▼]│  32768   │ ✕ │
│  │ glm-4      │ [文本▼]│  128000  │ ✕ │
│  └────────────┴────────┴──────────┘   │
│  [+ 添加模型]                         │
└───────────────────────────────────────┘
```

- **类型下拉选项**：文本 (text)、图像 (image)、代码 (code)、语音 (voice)
- **上下文长度**：可选数字输入，单位为 token 数，留空表示未知
- 每行末尾有删除按钮 ✕
- 点击「+ 添加模型」添加空行
- 至少需要添加 1 个模型才能提交（可选约束，见下）
- 提交时调 `bulkSetSupplierModels` 一次性保存所有模型

### 5.3 编辑供应商抽屉

与添加表单相同结构，打开时先 `GET /suppliers/{id}/models` 加载模型列表，编辑后提交时同样用 `bulkSetSupplierModels` 替换。

### 5.4 供应商卡片列表页

在每张供应商卡片上增加「支持模型」标签展示：

```
智能体
ms-abc***cdef
📝 qwen-max (32K) · 📝 glm-4 (128K)    ← 模型标签，最多显示 3 个，超出显示 "+N"
```

- 标签可带类型图标：📝 文本、🖼️ 图像、💻 代码、🔊 语音
- 标签附带上下文长度（单位 K token），无此信息时不显示
- 已禁用供应商的模型标签置灰

### 5.5 模型类型枚举

前端硬编码枚举（前后端对齐）：

```javascript
const MODEL_TYPES = [
  { value: 'text', label: '文本', icon: '📝' },
  { value: 'image', label: '图像', icon: '🖼️' },
  { value: 'code', label: '代码', icon: '💻' },
  { value: 'voice', label: '语音', icon: '🔊' },
]
```

后端 `SupplierModelCreate` 的 `model_type` 字段建议做校验（枚举白名单），避免脏数据。

## 6. 向后兼容

- **现有供应商**：添加功能上线后，已有供应商的 supplier_models 为空。LoadBalancer 在候选列表为空时应 fallback 到"不校验模型"的旧行为，或提示管理员配置模型。推荐方案：**候选为空时 fallback 到所有活跃供应商**（保持向后兼容，已有供应商可继续使用），并记录 warning 日志。
- **model_mappings 表**：完全不改动，别名解析继续工作。
- **已有 API 消费者**：`GET /suppliers` 返回的响应增加 `models` 字段（可选），不影响现有字段。

## 7. 错误处理

| 场景 | 行为 |
|------|------|
| 请求的模型没有任何供应商支持 | fallback 到所有活跃供应商（向后兼容），记录 warning |
| 添加供应商时模型名重复 | 409，提示该模型已添加 |
| 删除供应商 | CASCADE 自动清理 supplier_models |
| model_type 不在白名单 | 422，提示支持的类型列表 |

## 8. 测试计划

### 后端测试
- `SupplierModelRepository` CRUD 单元测试
- 删除供应商时 CASCADE 清理验证
- `find_suppliers_for_model` 只返回 active 供应商
- LoadBalancer 只从支持模型的供应商中选择
- LoadBalancer fallback 到所有活跃供应商（向后兼容）
- AliasResolver 从 model_mappings 解析别名

### 前端测试
- 添加供应商时模型列表渲染和提交
- 编辑供应商时模型列表加载和保存
- 卡片模型标签展示（截断 + "+N"）
- 类型下拉选项正确显示

### 集成测试
- 完整链路：别名 → 解析 → 供应商筛选 → 负载均衡 → 请求

## 9. 文件变更清单

| 文件 | 变更 |
|------|------|
| `core/database.py` | 新增 supplier_models 表 + 索引 |
| `repositories/supplier_model_repository.py` | 新增 |
| `services/load_balancer.py` | 修改 select_account，注入 SupplierModelRepository |
| `services/admin_service.py` | 新增供应商模型 CRUD 方法 |
| `api/admin_routes.py` | 新增 /suppliers/{id}/models 端点 |
| `api/routes.py` | 修改 load_balancer.select_account 调用 |
| `models/alias_resolver.py` | 修改 resolve_alias 使用 MappingRepository |
| `core/service_init.py` | 初始化 SupplierModelRepository |
| `web/src/api/index.js` | 新增供应商模型 API 函数 |
| `web/src/pages/Accounts.vue` | 添加/编辑表单增加模型区域，卡片展示模型标签 |
| `tests/` | 新增相关测试 |

## 10. 不做的事（YAGNI）

- 不新增独立的「供应商×模型」管理页面，管理入口完全在供应商页面
- 不使用 model_alias_cache 缓存表（暂不需要）
- 不修改 ModelScopeAccount dataclass 结构
- 不引入新的鉴权/权限机制
- 不在 model_mappings 表中增加供应商关联字段
- supplier_models 不记录区域信息（region），模型关联是全局的
