# 虚拟模型实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将「模型映射」重新定位为「虚拟模型」，使虚拟模型ID可绑定多个供应商模型，请求时按全局策略在绑定条目中分发。

**Architecture:** 新增 `AliasRouter` 服务（`services/alias_router.py`），封装"查绑定 → 按策略选一条目 → 返回(account, model_name)"的职责。`/chat/completions` 先调 alias_router，无绑定时 fallback 到旧流程（LB + alias_resolver）。前端 Mappings.vue 改为虚拟模型语义，内联绑定编辑区。

**Tech Stack:** Python (FastAPI), Vue 3 (Composition API), Tailwind CSS, SQLite, pytest

## Global Constraints

- 不修改 `mapping_models` 表结构
- 不删除 `actual_model_id` 列（保留数据用于 fallback）
- 不重命名 Mappings.vue 文件（只改展示名）
- 策略从 `system_config.load_balancer_strategy` 实时读取
- 无绑定时保持旧流程行为不变
- 测试使用独立测试数据库（`tests/modelscope_proxy_test.db`）
- 遵循现有代码风格：dataclass、type hints、logging

---

## 文件结构

### 新建
- `services/alias_router.py` — AliasRouter 服务 + RoutingResult dataclass
- `tests/services/test_alias_router.py` — AliasRouter 单元测试

### 修改（后端）
- `core/service_init.py` — 构建 AliasRouter 并挂载到 services
- `main.py` — lifespan 中挂载 alias_router 到 app.state
- `api/routes.py` — `/chat/completions` 先调 alias_router
- `repositories/mapping_repository.py` — bulk_upsert 兼容空 actual_model_id
- `services/admin_service.py` — 删除 `resolve_mapping_alias` 旧代码

### 修改（前端）
- `web/src/pages/Mappings.vue` — 标题/字段重命名；内联绑定区域；列表展开详情
- `web/src/components/MappingModelSelector.vue` — 改为可内联复用（或直接内联进 Mappings.vue）

---

## Task 1: AliasRouter 服务 + 测试

**Files:**
- Create: `services/alias_router.py`
- Create: `tests/services/test_alias_router.py`

**Interfaces:**
- Consumes: `mapping_model_repo.find_by_alias(alias)`, `account_repo.find_by_id(supplier_id)`, `config_repo.get("load_balancer_strategy")`
- Produces: `RoutingResult(account: ModelScopeAccount, model_name: str)` 或 `None`

- [ ] **Step 1: 写失败的测试**

创建 `tests/services/test_alias_router.py`：

```python
"""Test cases for AliasRouter."""
import pytest
from provider.services.alias_router import AliasRouter, RoutingResult
from provider.models.account import ModelScopeAccount


class MockMappingModelRepo:
    def __init__(self, entries):
        # entries: dict[alias, list[dict]]
        self._entries = entries

    def find_by_alias(self, alias):
        return self._entries.get(alias, [])


class MockAccountRepo:
    def __init__(self, accounts):
        # accounts: dict[id, dict]
        self._accounts = accounts

    def find_by_id(self, account_id):
        return self._accounts.get(account_id)


class MockConfigRepo:
    def __init__(self, strategy="round_robin"):
        self._strategy = strategy

    def get(self, key):
        if key == "load_balancer_strategy":
            return self._strategy
        return None


def _make_account(id, name="Supplier", api_key="key", base_url="https://api.test.com"):
    return {
        "id": id,
        "account_id": f"acc-{id}",
        "name": name,
        "api_key": api_key,
        "base_url": base_url,
        "status": "active",
    }


class TestAliasRouterRoute:
    """route() 方法的核心行为。"""

    def test_returns_none_when_no_bindings(self):
        """无绑定时返回 None。"""
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({}),
            account_repo=MockAccountRepo({}),
            config_repo=MockConfigRepo(),
        )
        result = router.route("unknown-alias")
        assert result is None

    def test_returns_none_when_bindings_but_no_valid_accounts(self):
        """有绑定但账号不存在时返回 None。"""
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [{"id": 1, "supplier_id": 999, "model_name": "qwen"}]
            }),
            account_repo=MockAccountRepo({}),  # 无账号
            config_repo=MockConfigRepo(),
        )
        result = router.route("my-alias")
        assert result is None

    def test_round_robin_selects_candidates(self):
        """round_robin 策略在候选间轮转。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("round_robin"),
        )
        r1 = router.route("my-alias")
        assert r1.account.account_id == "acc-1"
        assert r1.model_name == "qwen"
        r2 = router.route("my-alias")
        assert r2.account.account_id == "acc-2"
        assert r2.model_name == "gpt-4o"
        r3 = router.route("my-alias")
        assert r3.account.account_id == "acc-1"  # wraps

    def test_random_strategy_selects_from_candidates(self):
        """random 策略从候选中随机选。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("random"),
        )
        results = [router.route("my-alias") for _ in range(20)]
        model_names = {r.model_name for r in results}
        assert model_names == {"qwen", "gpt-4o"}

    def test_least_conn_strategy(self):
        """least_conn 策略选择连接数最少的候选。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("least_conn"),
        )
        # 第一次选第一个（都是 0 连接）
        r1 = router.route("my-alias")
        assert r1 is not None
        # 第二次选另一个
        r2 = router.route("my-alias")
        assert r2 is not None
        assert r1.model_name != r2.model_name

    def test_invalid_strategy_falls_back_to_round_robin(self):
        """无效策略名时 fallback 到 round_robin。"""
        accounts = {1: _make_account(1), 2: _make_account(2)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [
                    {"id": 1, "supplier_id": 1, "model_name": "qwen"},
                    {"id": 2, "supplier_id": 2, "model_name": "gpt-4o"},
                ]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo("invalid_strategy"),
        )
        r1 = router.route("my-alias")
        assert r1.model_name == "qwen"
        r2 = router.route("my-alias")
        assert r2.model_name == "gpt-4o"

    def test_result_is_routing_result_dataclass(self):
        """返回值是 RoutingResult 类型。"""
        accounts = {1: _make_account(1)}
        router = AliasRouter(
            mapping_model_repo=MockMappingModelRepo({
                "my-alias": [{"id": 1, "supplier_id": 1, "model_name": "qwen"}]
            }),
            account_repo=MockAccountRepo(accounts),
            config_repo=MockConfigRepo(),
        )
        result = router.route("my-alias")
        assert isinstance(result, RoutingResult)
        assert isinstance(result.account, ModelScopeAccount)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/services/test_alias_router.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'provider.services.alias_router'`

- [ ] **Step 3: 实现 AliasRouter**

创建 `services/alias_router.py`：

```python
"""AliasRouter — 根据虚拟模型ID的绑定条目选择路由。"""
import logging
import random
from dataclasses import dataclass
from typing import Optional

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
        # round_robin 计数器按 alias 隔离
        self._rr_counters = {}

    def _get_strategy(self) -> str:
        """从 system_config 实时读取策略，默认 round_robin。"""
        val = self.config_repo.get("load_balancer_strategy")
        if val in ("round_robin", "least_conn", "random"):
            return val
        return "round_robin"

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
            account_dict = self.account_repo.find_by_id(entry["supplier_id"])
            if account_dict:
                candidates.append((account_dict, entry["model_name"]))

        if not candidates:
            logger.warning(
                f"Alias '{alias}' has bindings but no valid accounts found"
            )
            return None

        strategy = self._get_strategy()

        if strategy == "round_robin":
            idx = self._round_robin_index(alias, len(candidates))
            selected = candidates[idx]
        elif strategy == "random":
            selected = random.choice(candidates)
        else:  # least_conn
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
        current = self._rr_counters.get(alias, 0)
        self._rr_counters[alias] = (current + 1) % size
        return current

    def _least_conn(self, alias: str, candidates):
        """least_conn 策略：选择当前连接数最少的候选。"""
        if not hasattr(self, "_conn_counts"):
            self._conn_counts = {}
        if alias not in self._conn_counts:
            self._conn_counts[alias] = [0] * len(candidates)
        counts = self._conn_counts[alias]
        # 候选数可能变化，补齐
        while len(counts) < len(candidates):
            counts.append(0)
        min_idx = counts.index(min(counts[:len(candidates)]))
        counts[min_idx] += 1
        return candidates[min_idx]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/services/test_alias_router.py -v`
Expected: 8 PASSED

- [ ] **Step 5: Commit**

```bash
git add services/alias_router.py tests/services/test_alias_router.py
git commit -m "feat: add AliasRouter service for virtual model routing"
```

---

## Task 2: 挂载 AliasRouter 到 app.state

**Files:**
- Modify: `core/service_init.py:48-73`
- Modify: `main.py:107-119`

**Interfaces:**
- Consumes: `mapping_model_repo`, `account_repo`（需新建）, `config_repo`（需新建）
- Produces: `services["alias_router"]`, `app.state.alias_router`

- [ ] **Step 1: 在 service_init.py 中构建 AliasRouter**

在 `initialize_all()` 方法中，在 `alias_resolver` 之后添加：

```python
# 在 service_init.py 顶部添加导入
from repositories.account_repository import AccountRepository
from repositories.config_repository import ConfigRepository
from services.alias_router import AliasRouter

# 在 initialize_all() 中，alias_resolver 之后
account_repo = AccountRepository(database)
config_repo = ConfigRepository(database)
alias_router = AliasRouter(
    mapping_model_repo=mapping_model_repo,
    account_repo=account_repo,
    config_repo=config_repo,
)
```

并在 `services` dict 中添加 `"alias_router": alias_router`。

- [ ] **Step 2: 在 main.py lifespan 中挂载到 app.state**

在 `lifespan()` 中，在 `app.state.admin_service = _admin_service` 之后添加：

```python
app.state.alias_router = _services["alias_router"]
```

- [ ] **Step 3: 运行现有测试确认无回归**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/ -v --timeout=30`
Expected: 全部通过（alias_router 不影响现有流程）

- [ ] **Step 4: Commit**

```bash
git add core/service_init.py main.py
git commit -m "feat: mount AliasRouter to app.state in service init"
```

---

## Task 3: 修改 /chat/completions 使用 AliasRouter

**Files:**
- Modify: `api/routes.py:325-570`

**Interfaces:**
- Consumes: `request.app.state.alias_router`（来自 Task 2）
- Produces: 无新增接口，仅改变内部路由逻辑

- [ ] **Step 1: 在 chat_completions 函数开头添加 alias_router 获取**

在 `chat_completions` 函数中，在 `admin_service = get_admin_service(fastapi_request)` 之后添加：

```python
alias_router = fastapi_request.app.state.alias_router
```

- [ ] **Step 2: 改造请求路由逻辑**

将现有流程（从 `# Select supplier using load balancer` 到 `actual_model_id = ...`）改为：

```python
# 1. 尝试绑定路由
route_result = alias_router.route(request.model)

if route_result is not None:
    # 2a. 有绑定 → 直接用路由结果
    selected_account = route_result.account
    actual_model_id = route_result.model_name
    logger.info(
        f"AliasRouter selected account {selected_account.account_id} "
        f"model {actual_model_id} for alias '{request.model}'"
    )
else:
    # 2b. 无绑定 → 旧流程
    selected_account = load_balancer.select_account(request.model)
    actual_model_id = await alias_resolver.resolve_alias(
        selected_account, request.model
    )
    logger.info(f"Resolved model {request.model} to {actual_model_id}")
```

- [ ] **Step 3: 运行现有测试确认无回归**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/api/test_routes.py -v`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add api/routes.py
git commit -m "feat: use AliasRouter in chat_completions for bound model routing"
```

---

## Task 4: 兼容空 actual_model_id

**Files:**
- Modify: `repositories/mapping_repository.py:42-56`

**Interfaces:**
- Consumes: `mappings: dict`（alias → actual_model_id，value 可能为空）
- Produces: 无新增接口

- [ ] **Step 1: 修改 bulk_upsert 兼容空 value**

在 `bulk_upsert` 方法中，将空值 fallback 到 alias_name：

```python
def bulk_upsert(self, mappings: dict):
    """Bulk upsert mappings from a dict like {'hy3': 'hy3-actual'}.

    Empty values fall back to the alias_name itself (virtual model ID
    is used as the actual model ID when no explicit mapping is given).
    """
    with self.db.get_connection() as conn:
        for alias_name, actual_model_id in mappings.items():
            # Fallback: empty value means use alias as actual model id
            effective_id = actual_model_id if actual_model_id else alias_name
            conn.execute(
                """INSERT INTO model_mappings (alias_name, actual_model_id)
                   VALUES (?, ?)
                   ON CONFLICT(alias_name)
                   DO UPDATE SET actual_model_id = excluded.actual_model_id""",
                (alias_name, effective_id),
            )
        logger.info(f"Bulk upserted {len(mappings)} model mappings")
```

- [ ] **Step 2: 运行现有测试确认无回归**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/repositories/ -v`
Expected: 全部通过

- [ ] **Step 3: Commit**

```bash
git add repositories/mapping_repository.py
git commit -m "fix: bulk_upsert handles empty actual_model_id (fallback to alias)"
```

---

## Task 5: 清理 admin_service 旧代码

**Files:**
- Modify: `services/admin_service.py:134-188`

**Interfaces:**
- 删除 `resolve_mapping_alias` 方法（已被 AliasRouter 替代）

- [ ] **Step 1: 删除 resolve_mapping_alias 方法**

在 `services/admin_service.py` 中，删除 `resolve_mapping_alias` 方法（第 134-188 行）。

- [ ] **Step 2: 确认无其他引用**

Run: `cd D:\workspace\ai\modelscope-provider && grep -rn "resolve_mapping_alias" --include="*.py" | grep -v __pycache__`
Expected: 无输出（或仅注释中提及）

- [ ] **Step 3: 运行测试确认无回归**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/ -v --timeout=30`
Expected: 全部通过

- [ ] **Step 4: Commit**

```bash
git add services/admin_service.py
git commit -m "chore: remove resolve_mapping_alias (replaced by AliasRouter)"
```

---

## Task 6: 前端 Mappings.vue 改造

**Files:**
- Modify: `web/src/pages/Mappings.vue:1-456`

**Interfaces:**
- Consumes: 现有 API（getMappings, bulkUpdateMappings, deleteMapping, getMappingModels, addMappingModel, removeMappingModel, getSuppliers）
- Produces: 无新增 API

- [ ] **Step 1: 改标题和按钮文案**

在 `<PageHeader>` 中：
- `title="模型映射"` → `title="虚拟模型"`
- `subtitle="管理模型别名与实际模型 ID 的映射关系"` → `subtitle="管理虚拟模型ID及其绑定的供应商模型"`
- 按钮 `添加映射` → `添加虚拟模型`

- [ ] **Step 2: 改表单字段名**

在表单 Drawer 中：
- `label="别名"` → `label="虚拟模型ID"`
- `placeholder="my-alias"` → `placeholder="my-virtual-model"`
- 删除 `actual_model_id` 字段（整个 `<div>` 包含 label + input）
- 删除 `form.value.model_id` 的引用（在 `submitForm` 中）

- [ ] **Step 3: 内联绑定模型区域**

在表单 Drawer 中，替换原有的"绑定模型"展示和"管理绑定模型"按钮，改为内联编辑区：

```html
<!-- ── 绑定模型（内联） ── -->
<div class="border-t border-ls-border pt-4 mt-4">
  <label class="form-label">绑定模型</label>
  <div class="flex items-end gap-2 mb-3">
    <div class="flex-1">
      <label class="text-xs text-gray-500 mb-1 block">供应商</label>
      <CSelect v-model="selectedSupplier" :options="supplierOptions" placeholder="选择供应商" />
    </div>
    <div class="flex-1">
      <label class="text-xs text-gray-500 mb-1 block">模型</label>
      <CSelect v-model="selectedModel" :options="modelOptions" placeholder="选择模型" />
    </div>
    <button @click="addBinding" class="btn btn-secondary" style="height: 38px;">添加</button>
  </div>

  <!-- 已绑定列表 -->
  <div v-if="bindingList.length > 0" class="tag-list">
    <div v-for="b in bindingList" :key="b.id" class="tag-item">
      <span>{{ b.supplier_name || `供应商${b.supplier_id}` }} / {{ b.model_name }}</span>
      <button @click="removeBinding(b.id)" class="tag-delete">×</button>
    </div>
  </div>
  <p v-else class="text-xs text-gray-500">暂无绑定模型，请求时将直接使用虚拟模型ID</p>
</div>
```

- [ ] **Step 4: 改列表卡片展示（数量+展开）**

在三种视图（row / grid / table）中，将"绑定模型 N 个"改为可展开的交互：

```html
<!-- row 视图中的绑定展示 -->
<div v-if="m.bound_models?.length" class="mt-1">
  <button @click="toggleExpand(m.alias_name)" class="text-xs text-gray-400 hover:text-ls-accent flex items-center gap-1">
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
      :class="expandedAlias === m.alias_name ? 'rotate-90' : ''" class="transition-transform">
      <polyline points="9 18 15 12 9 6"/>
    </svg>
    绑定 {{ m.bound_models.length }} 个模型
  </button>
  <div v-if="expandedAlias === m.alias_name" class="mt-2 pl-3 border-l border-ls-border space-y-1">
    <div v-for="b in m.bound_models" :key="b.id" class="flex items-center justify-between text-xs">
      <span class="text-gray-300">{{ b.supplier_name || `供应商${b.supplier_id}` }} / {{ b.model_name }}</span>
      <button @click.stop="removeBinding(m.alias_name, b.id)" class="text-gray-500 hover:text-red-400 ml-2">×</button>
    </div>
  </div>
</div>
```

- [ ] **Step 5: 添加相关响应式状态和方法**

在 `<script setup>` 中添加：

```javascript
import CSelect from '@/components/CSelect.vue'
import { getSuppliers } from '@/api'

// ── 展开状态 ──
const expandedAlias = ref(null)
const toggleExpand = (alias) => {
  expandedAlias.value = expandedAlias.value === alias ? null : alias
}

// ── 绑定模型 ──
const suppliers = ref([])
const selectedSupplier = ref(null)
const selectedModel = ref(null)
const bindingList = ref([])

const supplierOptions = computed(() =>
  suppliers.value.map(s => ({ label: s.name, value: s.id }))
)
const modelOptions = computed(() => {
  if (!selectedSupplier.value) return []
  const sup = suppliers.value.find(s => s.id === selectedSupplier.value)
  return (sup?.models || []).map(m => ({ label: m.model_name, value: m.model_name }))
})

const loadSuppliers = async () => {
  try {
    const res = await getSuppliers()
    suppliers.value = res.data || []
  } catch (e) {
    console.error('Failed to load suppliers:', e)
  }
}

const addBinding = async () => {
  if (!selectedSupplier.value || !selectedModel.value) {
    toast('请选择供应商和模型', 'error')
    return
  }
  if (bindingList.value.some(b => b.supplier_id === selectedSupplier.value && b.model_name === selectedModel.value)) {
    toast('该模型已添加', 'error')
    return
  }
  try {
    const alias = isEditing.value ? currentMapping.value.alias_name : form.value.alias
    const res = await addMappingModel(alias, {
      supplier_id: selectedSupplier.value,
      model_name: selectedModel.value,
    })
    bindingList.value.push({
      id: res.data.id,
      supplier_id: selectedSupplier.value,
      model_name: selectedModel.value,
      supplier_name: suppliers.value.find(s => s.id === selectedSupplier.value)?.name,
    })
  } catch (e) {
    toast('添加失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  }
}

const removeBinding = async (alias, modelId) => {
  try {
    await removeMappingModel(modelId)
    bindingList.value = bindingList.value.filter(b => b.id !== modelId)
    // 同步更新 mappings 列表中的 bound_models
    const m = mappings.value.find(m => m.alias_name === alias)
    if (m) m.bound_models = m.bound_models.filter(b => b.id !== modelId)
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  }
}
```

- [ ] **Step 6: 修改 openEdit 和 openAdd 以支持 bindingList**

```javascript
const openAdd = async () => {
  isEditing.value = false
  form.value = { alias: '' }
  bindingList.value = []
  selectedSupplier.value = null
  selectedModel.value = null
  showFormDrawer.value = true
  await nextTick()
  formAliasInput.value?.focus()
}

const openEdit = async (item) => {
  isEditing.value = true
  currentMapping.value = item
  form.value = { alias: item.alias_name }
  try {
    const res = await getMappingModels(item.alias_name)
    bindingList.value = (res.data || []).map(b => ({
      ...b,
      supplier_name: suppliers.value.find(s => s.id === b.supplier_id)?.name
    }))
  } catch (e) {
    console.error('Failed to load mapping models:', e)
  }
  showFormDrawer.value = true
}
```

- [ ] **Step 7: 修改 submitForm 移除 model_id 校验**

```javascript
const submitForm = async () => {
  if (!form.value.alias) {
    toast('请填写虚拟模型ID', 'error')
    return
  }
  submitting.value = true
  try {
    const allMappings = {}
    for (const m of mappings.value) {
      allMappings[m.alias_name] = m.actual_model_id || m.alias_name
    }
    allMappings[form.value.alias] = form.value.alias  // 虚拟模型ID 自身作为 actual_model_id
    await apiBulkUpdate(allMappings)
    await loadData()
    closeForm()
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    submitting.value = false
  }
}
```

- [ ] **Step 8: 在 onMounted 中加载 suppliers**

```javascript
onMounted(() => {
  loadData()
  loadSuppliers()
  document.addEventListener('keydown', handleKeyDown)
})
```

- [ ] **Step 9: 删除不再需要的代码**

- 删除 `showSelectorDrawer`、`openSelector`、`closeSelector`（第二个 Drawer 相关）
- 删除 `MappingModelSelector` 导入和使用
- 删除 `removeMappingModel` 旧方法（已被新的 `removeBinding` 替代）

- [ ] **Step 10: 运行前端构建确认无语法错误**

Run: `cd D:\workspace\ai\modelscope-provider/web && npm run build`
Expected: 构建成功

- [ ] **Step 11: Commit**

```bash
git add web/src/pages/Mappings.vue
git commit -m "feat: redesign Mappings page as Virtual Model with inline binding editor"
```

---

## Task 7: 清理 MappingModelSelector 组件

**Files:**
- Delete: `web/src/components/MappingModelSelector.vue`（如果已完全内联）
- 或 Modify: 保留但标注为 deprecated

**Interfaces:**
- 无（已被内联逻辑替代）

- [ ] **Step 1: 确认 MappingModelSelector 无其他引用**

Run: `cd D:\workspace\ai\modelscope-provider && grep -rn "MappingModelSelector" --include="*.vue" --include="*.js" | grep -v __pycache__`
Expected: 仅 Mappings.vue 中已删除

- [ ] **Step 2: 删除文件**

Run: `git rm web/src/components/MappingModelSelector.vue`

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: remove MappingModelSelector (inlined into Mappings.vue)"
```

---

## Task 8: 端到端验证

**Files:**
- 无新增文件，验证整体流程

- [ ] **Step 1: 启动后端服务**

Run: `cd D:\workspace\ai\modelscope-provider && python -m uvicorn main:app --reload --port 8000`
Expected: 服务启动无报错

- [ ] **Step 2: 验证健康检查**

Run: `curl http://localhost:8000/api/health`
Expected: `{"status": "healthy", ...}`

- [ ] **Step 3: 验证 admin API 正常**

Run: `curl http://localhost:8000/api/admin/mappings`
Expected: 返回映射列表（200）

- [ ] **Step 4: 运行全部测试**

Run: `cd D:\workspace\ai\modelscope-provider && python -m pytest tests/ -v --timeout=30`
Expected: 全部通过

- [ ] **Step 5: Commit（如有修复）**

```bash
git add -A
git commit -m "fix: e2e verification fixes" --allow-empty
```

---

## 测试策略

| 测试类型 | 覆盖点 |
|---------|--------|
| AliasRouter 单元测试 | 无绑定、无有效账号、round_robin、random、least_conn、无效策略 fallback |
| 现有测试回归 | 确保旧流程（无绑定时）行为不变 |
| 前端构建 | `npm run build` 无语法错误 |
| 端到端 | 服务启动、健康检查、admin API 正常 |

---

## 风险与回滚

- **风险**：AliasRouter 策略读取失败 → 已用 try/except 包裹，fallback 到 round_robin
- **回滚**：如新逻辑有问题，可在 routes.py 中临时注释 alias_router.route() 调用，恢复旧流程
- **数据**：无迁移，无列改动，完全可逆
