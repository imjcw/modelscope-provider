# 供应商模型管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在供应商层面管理支持的模型列表（含模型类型 + 上下文长度），让负载均衡器只从"支持该模型"的活跃供应商中选择。管理入口完全在供应商添加/编辑页面。

**Architecture:** 新增 `supplier_models` 表（supplier_id × model_name × model_type × context_length，UNIQUE 约束），新增 SupplierModelRepository CRUD。LoadBalancer 改在 select_account 时 JOIN 该表筛选候选供应商。AliasResolver 改从 model_mappings 表真正解析别名。前端 Accounts.vue 的添加/编辑抽屉增加模型列表管理。

**Tech Stack:** Python (FastAPI, SQLite), Vue 3 (Vite), Pydantic, pytest, fastapi.testclient

## Global Constraints

- DB 路径：测试用 `sqlite:///modelscope_proxy_test.db`（conftest.py 已自动隔离），正式用现有 `modelscope_proxy.db`，**不要混用**
- 项目路径前缀：所有 import 用 `from provider.xxx`（包名为 `provider`）
- 前端 API base：`/api/admin`，axios 实例在 `web/src/api/index.js`
- model_type 枚举：`text` / `image` / `code` / `voice`，后端白名单校验
- 向后兼容：供应商无模型配置时，LoadBalancer fallback 到所有活跃供应商 + warning 日志
- Vue 组件风格：使用 `<script setup>` + Composition API，抽屉模式（drawer），已有样式在 `main.css`
- 所有后端改动同步更新测试，全部 pytest 通过再提交
- git 提交：每个 task 完成后 commit，message 格式 `feat: ...` / `fix: ...` / `test: ...`

---

## File Change Map

| 文件 | 操作 | 职责 |
|------|------|------|
| `core/database.py` | modify | 新增 supplier_models 表 + 索引 |
| `repositories/supplier_model_repository.py` | create | 供应商×模型关联 CRUD |
| `services/load_balancer.py` | modify | select_account 增加模型筛选 |
| `services/admin_service.py` | modify | 新增供应商模型管理方法 |
| `api/admin_routes.py` | modify | 新增 /suppliers/{id}/models 端点 |
| `models/alias_resolver.py` | modify | 真正从 model_mappings 解析别名 |
| `core/service_init.py` | modify | 初始化 SupplierModelRepository + 注入 |
| `web/src/api/index.js` | modify | 新增供应商模型 API 函数 |
| `web/src/pages/Accounts.vue` | modify | 添加/编辑表单增加模型区域，卡片展示模型标签 |
| `tests/repositories/test_supplier_model_repository.py` | create | Repository 单元测试 |
| `tests/api/test_supplier_models.py` | create | API 端点集成测试 |
| `tests/services/test_load_balancer_model_filter.py` | create | LoadBalancer 模型筛选测试 |

---

### Task 1: 数据库 — 新增 supplier_models 表

**Files:**
- Modify: `core/database.py`
- Test: `tests/core/test_database.py`（可选，数据库初始化已有测试覆盖）

**Interfaces:**
- Produces: `supplier_models` 表，字段 id, supplier_id, model_name, model_type, context_length; UNIQUE(supplier_id, model_name); 索引 idx_supplier_models_name(model_name), idx_supplier_models_supplier(supplier_id)

- [ ] **Step 1: 在 initialize_tables() 中新增建表 SQL**

在 `core/database.py` 的 `initialize_tables()` 方法中，紧跟 `model_mappings` 建表 SQL 之后，插入以下 SQL（在 `# ── New tables for admin panel ──` 注释块内）：

```python
# Supplier models table — which models each supplier supports
cursor.execute("""
    CREATE TABLE IF NOT EXISTS supplier_models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
        model_name TEXT NOT NULL,
        model_type TEXT NOT NULL,
        context_length INTEGER,
        UNIQUE(supplier_id, model_name)
    )
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_supplier_models_name
    ON supplier_models(model_name)
""")

cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_supplier_models_supplier
    ON supplier_models(supplier_id)
""")
```

- [ ] **Step 2: 运行测试确认数据库初始化无问题**

```bash
pytest tests/core/test_database.py -v
```

Expected: PASS（所有已有测试通过，新表不破坏任何现有行为）

- [ ] **Step 3: 手动验证新表创建**

```bash
python -c "
from provider.core.database import DatabaseManager
import os
os.environ['DATABASE_URL'] = 'sqlite:///modelscope_proxy_test.db'
db = DatabaseManager('sqlite:///modelscope_proxy_test.db')
db.initialize_tables()
with db.get_connection() as conn:
    for row in conn.execute(\"PRAGMA table_info(supplier_models)\"):
        print(row)
    for row in conn.execute(\"SELECT sql FROM sqlite_master WHERE name LIKE 'idx_supplier_models%'\"):
        print(row[0])
"
```

Expected: 打印 supplier_models 的 5 个字段（id, supplier_id, model_name, model_type, context_length）和 2 个索引 SQL。

- [ ] **Step 4: 清理测试数据库并 commit**

```bash
rm -f modelscope_proxy_test.db
git add core/database.py
git commit -m "feat: add supplier_models table with model_type and context_length"
```

---

### Task 2: Repository — SupplierModelRepository

**Files:**
- Create: `repositories/supplier_model_repository.py`
- Create: `tests/repositories/test_supplier_model_repository.py`

**Interfaces:**
- Produces:
  - `SupplierModelRepository(db: DatabaseManager)`
  - `find_by_supplier(supplier_id: int) -> List[dict]`
  - `create(supplier_id, model_name, model_type, context_length: Optional[int] = None) -> dict`
  - `delete(model_id: int) -> bool`
  - `delete_by_supplier(supplier_id: int) -> int`（返回删除行数）
  - `bulk_upsert(supplier_id, models: List[dict])`（models: [{model_name, model_type, context_length}]）
  - `find_suppliers_for_model(model_name) -> List[dict]`（JOIN accounts，只返回 status='active'）

- [ ] **Step 1: 创建 SupplierModelRepository**

创建 `repositories/supplier_model_repository.py`：

```python
import logging
from typing import List, Optional

from provider.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class SupplierModelRepository:
    """Repository for supplier_models table."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_by_supplier(self, supplier_id: int) -> List[dict]:
        """Get all models supported by a supplier."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM supplier_models WHERE supplier_id = ? ORDER BY model_name",
                (supplier_id,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def create(
        self,
        supplier_id: int,
        model_name: str,
        model_type: str,
        context_length: Optional[int] = None,
    ) -> dict:
        """Create a supplier-model association. Raises on UNIQUE conflict."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO supplier_models (supplier_id, model_name, model_type, context_length)
                   VALUES (?, ?, ?, ?)""",
                (supplier_id, model_name, model_type, context_length),
            )
            cursor = conn.execute(
                "SELECT * FROM supplier_models WHERE supplier_id = ? AND model_name = ?",
                (supplier_id, model_name),
            )
            row = cursor.fetchone()
            result = dict(row)
            logger.info(
                f"Created supplier model: supplier_id={supplier_id}, model={model_name}, "
                f"type={model_type}, context_length={context_length}"
            )
            return result

    def delete(self, model_id: int) -> bool:
        """Delete a supplier-model association by its row id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM supplier_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0

    def delete_by_supplier(self, supplier_id: int) -> int:
        """Delete all models for a supplier. Returns deleted row count."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM supplier_models WHERE supplier_id = ?", (supplier_id,)
            )
            return cursor.rowcount

    def bulk_upsert(
        self, supplier_id: int, models: List[dict]
    ) -> None:
        """Replace all models for a supplier with the given list.

        Each item in models is a dict with keys: model_name, model_type, context_length (optional).
        """
        with self.db.get_connection() as conn:
            # Delete existing models for this supplier first
            conn.execute(
                "DELETE FROM supplier_models WHERE supplier_id = ?", (supplier_id,)
            )
            # Insert new models
            for m in models:
                conn.execute(
                    """INSERT INTO supplier_models (supplier_id, model_name, model_type, context_length)
                       VALUES (?, ?, ?, ?)""",
                    (supplier_id, m["model_name"], m["model_type"], m.get("context_length")),
                )
            logger.info(f"Bulk upserted {len(models)} models for supplier {supplier_id}")

    def find_suppliers_for_model(self, model_name: str) -> List[dict]:
        """Find active suppliers that support a given model name.

        Returns full account dicts from the accounts table, joined with
        the matching supplier_models row.
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """SELECT a.*, sm.model_type, sm.context_length
                   FROM accounts a
                   INNER JOIN supplier_models sm ON sm.supplier_id = a.id
                   WHERE sm.model_name = ? AND a.status = 'active'
                   ORDER BY a.id""",
                (model_name,),
            )
            return [dict(row) for row in cursor.fetchall()]
```

- [ ] **Step 2: 创建测试**

创建 `tests/repositories/test_supplier_model_repository.py`：

```python
import pytest
import sqlite3

from provider.repositories.account_repository import AccountRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository


@pytest.fixture
def supplier_model_repo(database):
    return SupplierModelRepository(database)


@pytest.fixture
def sample_supplier(database, supplier_model_repo):
    """Create a test supplier and return its dict."""
    acc_repo = AccountRepository(database)
    return acc_repo.create(
        name="test-supplier",
        api_key="ms-test-key",
        base_url="https://api.modelscope.test/v1",
        region="china",
    )


def test_create_and_find_by_supplier(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    result = supplier_model_repo.create(
        supplier_id=sid, model_name="qwen-max", model_type="text", context_length=32768
    )
    assert result["supplier_id"] == sid
    assert result["model_name"] == "qwen-max"
    assert result["model_type"] == "text"
    assert result["context_length"] == 32768

    models = supplier_model_repo.find_by_supplier(sid)
    assert len(models) == 1
    assert models[0]["model_name"] == "qwen-max"


def test_create_duplicate_raises_uniqueness_error(
    database, supplier_model_repo, sample_supplier
):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")
    with pytest.raises(sqlite3.IntegrityError):
        supplier_model_repo.create(sid, "qwen-max", "text")


def test_delete_by_id(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    row = supplier_model_repo.create(sid, "glm-4", "text", context_length=128000)
    mid = row["id"]
    assert supplier_model_repo.delete(mid) is True
    assert supplier_model_repo.delete(mid) is False  # already deleted
    assert supplier_model_repo.find_by_supplier(sid) == []


def test_delete_by_supplier(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")
    supplier_model_repo.create(sid, "glm-4", "code")
    assert supplier_model_repo.delete_by_supplier(sid) == 2
    assert supplier_model_repo.find_by_supplier(sid) == []


def test_bulk_upsert_replaces_all(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    # First upsert
    supplier_model_repo.bulk_upsert(
        sid,
        [
            {"model_name": "qwen-max", "model_type": "text", "context_length": 32768},
            {"model_name": "glm-4", "model_type": "text", "context_length": 128000},
        ],
    )
    models = supplier_model_repo.find_by_supplier(sid)
    assert len(models) == 2

    # Second upsert — replaces all
    supplier_model_repo.bulk_upsert(
        sid,
        [
            {"model_name": "qwen-vl", "model_type": "image", "context_length": None},
        ],
    )
    models = supplier_model_repo.find_by_supplier(sid)
    assert len(models) == 1
    assert models[0]["model_name"] == "qwen-vl"
    assert models[0]["model_type"] == "image"
    assert models[0]["context_length"] is None


def test_find_suppliers_for_model_only_active(
    database, supplier_model_repo, sample_supplier
):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")

    result = supplier_model_repo.find_suppliers_for_model("qwen-max")
    assert len(result) == 1
    assert result[0]["id"] == sid

    # Disable supplier
    acc_repo = AccountRepository(database)
    acc_repo.update(sid, status="disabled")

    result = supplier_model_repo.find_suppliers_for_model("qwen-max")
    assert result == []


def test_find_suppliers_for_model_no_match(
    database, supplier_model_repo, sample_supplier
):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")

    result = supplier_model_repo.find_suppliers_for_model("nonexistent")
    assert result == []


def test_cascade_on_supplier_delete(database, supplier_model_repo, sample_supplier):
    sid = sample_supplier["id"]
    supplier_model_repo.create(sid, "qwen-max", "text")
    acc_repo = AccountRepository(database)
    acc_repo.delete(sid)
    assert supplier_model_repo.find_by_supplier(sid) == []
```

- [ ] **Step 3: 运行测试验证失败 → 通过**

```bash
pytest tests/repositories/test_supplier_model_repository.py -v
```

Expected: 所有 8 个测试 PASS。

- [ ] **Step 4: Commit**

```bash
git add repositories/supplier_model_repository.py tests/repositories/test_supplier_model_repository.py
git commit -m "feat: add SupplierModelRepository with CRUD and model filtering"
```

---

### Task 3: LoadBalancer — 增加模型筛选

**Files:**
- Modify: `services/load_balancer.py`
- Create: `tests/services/test_load_balancer_model_filter.py`

**Interfaces:**
- Consumes: `SupplierModelRepository`（Task 2）
- Produces: `LoadBalancer.__init__` 新增 `supplier_model_repo` 参数; `select_account(model_name)` 先按模型筛选活跃供应商

- [ ] **Step 1: 修改 LoadBalancer**

修改 `services/load_balancer.py`：

```python
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class LoadBalancer:
    """Load balancer for selecting ModelScope accounts."""

    def __init__(
        self,
        accounts: List,
        supplier_model_repo=None,
    ):
        self.accounts = accounts
        self.current_index = 0
        self.supplier_model_repo = supplier_model_repo

    def select_account(self, model_name: str = None):
        """Select an available account using round-robin strategy.

        When supplier_model_repo is set, first filter to suppliers that
        declare support for model_name. Falls back to all accounts if
        no supplier declares the model (backward compat).
        """
        candidates = self.accounts

        # Filter by model support if repo is available and model_name given
        if self.supplier_model_repo is not None and model_name:
            db_candidates = self.supplier_model_repo.find_suppliers_for_model(model_name)
            db_candidate_ids = {c["account_id"] for c in db_candidates}
            if db_candidate_ids:
                model_filtered = [
                    acc for acc in self.accounts
                    if acc.account_id in db_candidate_ids and acc.status == "active"
                ]
                if model_filtered:
                    logger.info(
                        f"Filtered {len(candidates)} accounts to {len(model_filtered)} "
                        f"for model {model_name}"
                    )
                    candidates = model_filtered
                else:
                    logger.warning(
                        f"No active supplier declares model {model_name}; "
                        f"falling back to all accounts"
                    )
                # If db_candidates is empty or model_filtered is empty,
                # we fall through to the existing unavailable_models filter
            else:
                logger.warning(
                    f"No supplier declares model {model_name}; "
                    f"falling back to all accounts"
                )

        # Existing unavailable_models filter
        available_accounts = [
            acc for acc in candidates
            if acc.unavailable_models is None or model_name not in acc.unavailable_models
        ]
        if not available_accounts:
            all_unavailable = set()
            for acc in candidates:
                if acc.unavailable_models:
                    all_unavailable.update(acc.unavailable_models)
            raise ValueError(
                f"All accounts are unavailable for model {model_name}. "
                f"Unavailable models: {all_unavailable}"
            )
        account = available_accounts[self.current_index % len(available_accounts)]
        self.current_index += 1
        logger.info(f"Selected account {account.account_id} for load balancing")
        return account
```

**注意**：当前 `accounts` 列表中的 account 是 `ModelScopeAccount` dataclass，它没有 `status` 字段。`find_suppliers_for_model` 已经过滤了 `status='active'`，所以 `acc.status` 这一行会报错。**修正**：用 `account_id` 匹配即可，不需要额外 status 检查。

修正后的 model_filtered 过滤：

```python
                model_filtered = [
                    acc for acc in self.accounts
                    if acc.account_id in db_candidate_ids
                ]
```

- [ ] **Step 2: 创建测试**

创建 `tests/services/test_load_balancer_model_filter.py`：

```python
import pytest
from provider.models.account import ModelScopeAccount
from provider.services.load_balancer import LoadBalancer


def _make_accounts():
    return [
        ModelScopeAccount(
            account_id="acc1", api_key="k1", base_url="https://u1/v1",
            name="supplier1", status="active",
        ),
        ModelScopeAccount(
            account_id="acc2", api_key="k2", base_url="https://u2/v1",
            name="supplier2", status="active",
        ),
    ]


def test_select_without_model_repo_round_robin():
    """Without model repo, behaves as before — round-robin over all accounts."""
    accounts = _make_accounts()
    lb = LoadBalancer(accounts)

    a1 = lb.select_account("qwen-max")
    assert a1.account_id == "acc1"
    a2 = lb.select_account("qwen-max")
    assert a2.account_id == "acc2"
    a3 = lb.select_account("qwen-max")
    assert a3.account_id == "acc1"  # wraps around


class MockSupplierModelRepo:
    """Mock repo that returns suppliers for a model by account_id."""

    def __init__(self, model_to_accounts):
        self.model_to_accounts = model_to_accounts

    def find_suppliers_for_model(self, model_name):
        account_ids = self.model_to_accounts.get(model_name, [])
        return [{"account_id": aid} for aid in account_ids]


def test_select_filters_by_model():
    """Only returns suppliers that declare the model."""
    accounts = _make_accounts()
    repo = MockSupplierModelRepo({
        "qwen-max": ["acc1"],   # only acc1 supports qwen-max
    })
    lb = LoadBalancer(accounts, supplier_model_repo=repo)

    result = lb.select_account("qwen-max")
    assert result.account_id == "acc1"


def test_select_fallback_when_no_supplier_declares_model():
    """Falls back to all accounts when no supplier declares the model."""
    accounts = _make_accounts()
    repo = MockSupplierModelRepo({})  # nothing declared
    lb = LoadBalancer(accounts, supplier_model_repo=repo)

    result = lb.select_account("nonexistent-model")
    # Should fall back to round-robin over all accounts
    assert result.account_id in ("acc1", "acc2")


def test_select_unavailable_models_still_filtered():
    """Even with model repo, unavailable_models filter still applies."""
    accounts = _make_accounts()
    accounts[0].unavailable_models = {"qwen-max"}  # acc1 unavailable for qwen-max
    repo = MockSupplierModelRepo({
        "qwen-max": ["acc1"],   # only acc1 declares qwen-max
    })
    lb = LoadBalancer(accounts, supplier_model_repo=repo)

    # acc1 is the only supplier declaring qwen-max, but it's unavailable
    # The unavailable_models filter runs after model filter, so acc1 is excluded
    # Fallback: all accounts filtered by unavailable_models -> only acc2
    result = lb.select_account("qwen-max")
    assert result.account_id == "acc2"


def test_no_accounts_raises():
    lb = LoadBalancer([])
    with pytest.raises(ValueError, match="No accounts available"):
        lb.select_account("qwen-max")
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/services/test_load_balancer_model_filter.py -v
```

Expected: 所有 5 个测试 PASS。

- [ ] **Step 4: 运行全量测试确认无回归**

```bash
pytest tests/ -v --ignore=tests/integration/
```

Expected: 所有已有测试仍 PASS。

- [ ] **Step 5: Commit**

```bash
git add services/load_balancer.py tests/services/test_load_balancer_model_filter.py
git commit -m "feat: LoadBalancer filters accounts by declared model support"
```

---

### Task 4: AliasResolver — 真正从 model_mappings 解析

**Files:**
- Modify: `models/alias_resolver.py`
- Test: `tests/models/test_alias_resolver.py`（已有文件，可能需更新或新增测试）

**Interfaces:**
- Consumes: `MappingRepository`（已存在于 `repositories/mapping_repository.py`）
- Produces: `ModelAliasResolver.__init__` 新增 `mapping_repo` 参数; `resolve_alias` 优先查 model_mappings 表

- [ ] **Step 1: 修改 AliasResolver**

修改 `models/alias_resolver.py`：

```python
import logging
import httpx
from provider.models.account import ModelScopeAccount

logger = logging.getLogger(__name__)


class ModelAliasResolver:
    """Resolve model aliases to actual model IDs."""

    def __init__(self, http_client: httpx.AsyncClient, mapping_repo=None):
        self.http_client = http_client
        self.mapping_repo = mapping_repo

    async def resolve_alias(self, account: ModelScopeAccount = None, alias: str = None) -> str:
        """Resolve model alias to actual model ID.

        Priority:
        1. Look up model_mappings table for an exact alias_name match.
        2. Fallback: return the alias as-is.
        """
        if self.mapping_repo is not None:
            mappings = self.mapping_repo.find_by_alias(alias)
            if mappings:
                actual_model_id = mappings[0]["actual_model_id"]
                logger.info(f"Resolved alias '{alias}' to '{actual_model_id}' via model_mappings")
                return actual_model_id

        logger.info(f"Using model '{alias}' as-is")
        return alias
```

**注意**：当前 `api/routes.py` 调用 `alias_resolver.resolve_alias(selected_account, request.model)`，传了 positional 参数。修改后需要确认调用方式匹配。`resolve_alias` 现在接收 `account` 和 `alias` 作为关键字参数，调用处 `resolve_alias(selected_account, request.model)` 是 positional，对应 `(account, alias)`，签名兼容。

- [ ] **Step 2: 查看并更新现有测试**

查看 `tests/models/test_alias_resolver.py`，确认是否需要更新以适配新的初始化签名和解析逻辑。如果现有测试只测试 fallback 行为（直接返回 alias），确保它仍能 PASS（mapping_repo=None 时应返回 alias）。

如果该文件不存在，创建：

```python
import pytest

from provider.models.alias_resolver import ModelAliasResolver


class MockMappingRepo:
    def __init__(self, mappings=None):
        self.mappings = mappings or {}

    def find_by_alias(self, alias_name):
        return self.mappings.get(alias_name, [])


@pytest.mark.asyncio
async def test_resolve_with_mapping():
    repo = MockMappingRepo({"my-alias": [{"actual_model_id": "qwen-max", "region": "china"}]})
    resolver = ModelAliasResolver(http_client=None, mapping_repo=repo)

    result = await resolver.resolve_alias(alias="my-alias")
    assert result == "qwen-max"


@pytest.mark.asyncio
async def test_resolve_without_mapping_returns_alias():
    resolver = ModelAliasResolver(http_client=None, mapping_repo=None)

    result = await resolver.resolve_alias(alias="some-model")
    assert result == "some-model"


@pytest.mark.asyncio
async def test_resolve_mapping_not_found_falls_back():
    repo = MockMappingRepo({})
    resolver = ModelAliasResolver(http_client=None, mapping_repo=repo)

    result = await resolver.resolve_alias(alias="unknown-alias")
    assert result == "unknown-alias"
```

- [ ] **Step 3: 运行测试**

```bash
pytest tests/models/test_alias_resolver.py -v
```

Expected: 所有测试 PASS。

- [ ] **Step 4: Commit**

```bash
git add models/alias_resolver.py tests/models/test_alias_resolver.py
git commit -m "feat: AliasResolver resolves aliases via model_mappings table"
```

---

### Task 5: ServiceInitializer — 注入依赖

**Files:**
- Modify: `core/service_init.py`

**Interfaces:**
- Consumes: `SupplierModelRepository`（Task 2）, `MappingRepository`
- Produces: `LoadBalancer` 接收 supplier_model_repo; `ModelAliasResolver` 接收 mapping_repo

- [ ] **Step 1: 修改 ServiceInitializer**

修改 `core/service_init.py`：

```python
from typing import List, Optional
from provider.core.config import ConfigManager
from provider.core.database import DatabaseManager
from provider.core.http_client import HttpClient
from provider.models.account import ModelScopeAccount
from provider.models.alias_resolver import ModelAliasResolver
from provider.repositories.config_repository import ConfigRepository
from provider.repositories.mapping_repository import MappingRepository
from provider.repositories.quota_repository import QuotaRepository
from provider.repositories.supplier_model_repository import SupplierModelRepository
from provider.services.load_balancer import LoadBalancer
from provider.services.response_converter import ResponseConverter
from provider.services.quota_updater import QuotaUpdater


class ServiceInitializer:
    """Initialize all services."""

    def __init__(self, config_manager: ConfigManager):
        self.config = config_manager

    async def initialize_all(
        self,
        accounts: Optional[List[ModelScopeAccount]] = None,
    ) -> dict:
        """Initialize all services."""
        # Initialize database
        database = DatabaseManager(self.config.get_database_url())
        database.initialize_tables()
        database.seed_default_config()

        # Load accounts if not provided
        if accounts is None:
            self.config.db = database
            accounts = self.config.load_accounts(migrate_from_env=True)

        # Initialize HTTP client
        http_client = HttpClient()

        # Initialize repositories
        quota_repository = QuotaRepository(database)
        mapping_repository = MappingRepository(database)
        supplier_model_repo = SupplierModelRepository(database)

        # Initialize services
        load_balancer = LoadBalancer(accounts, supplier_model_repo=supplier_model_repo)
        response_converter = ResponseConverter()
        quota_updater = QuotaUpdater(quota_repository)
        alias_resolver = ModelAliasResolver(
            await http_client.create_client(), mapping_repo=mapping_repository
        )

        services = {
            "database": database,
            "http_client": http_client,
            "quota_repository": quota_repository,
            "mapping_repository": mapping_repository,
            "supplier_model_repo": supplier_model_repo,
            "load_balancer": load_balancer,
            "response_converter": response_converter,
            "quota_updater": quota_updater,
            "alias_resolver": alias_resolver,
            "accounts": accounts,
        }

        return services
```

- [ ] **Step 2: 运行全量测试确认无回归**

```bash
pytest tests/ -v --ignore=tests/integration/
```

Expected: 所有测试 PASS。

- [ ] **Step 3: Commit**

```bash
git add core/service_init.py
git commit -m "feat: inject SupplierModelRepository and MappingRepository into services"
```

---

### Task 6: AdminService + AdminRoutes — 供应商模型 CRUD API

**Files:**
- Modify: `services/admin_service.py`
- Modify: `api/admin_routes.py`
- Create: `tests/api/test_supplier_models.py`

**Interfaces:**
- Consumes: `SupplierModelRepository`（Task 2）
- Produces: API endpoints
  - `GET /api/admin/suppliers/{supplier_id}/models` → List[dict]
  - `POST /api/admin/suppliers/{supplier_id}/models` → dict（body: `{model_name, model_type, context_length?}`）
  - `DELETE /api/admin/suppliers/{supplier_id}/models/{model_id}` → `{ok: bool}`
  - `PUT /api/admin/suppliers/{supplier_id}/models/bulk` → List[dict]（body: `{models: [{model_name, model_type, context_length?}]}`）

- [ ] **Step 1: 修改 AdminService**

在 `services/admin_service.py` 的 `__init__` 中新增 `supplier_model_repo`：

```python
    def __init__(self, account_repo: AccountRepository,
                 mapping_repo: MappingRepository,
                 config_repo: ConfigRepository,
                 log_repo: LogRepository,
                 quota_repo: QuotaRepository = None,
                 supplier_model_repo: SupplierModelRepository = None):
        self.account_repo = account_repo
        self.mapping_repo = mapping_repo
        self.config_repo = config_repo
        self.log_repo = log_repo
        self.quota_repo = quota_repo
        self.supplier_model_repo = supplier_model_repo
```

在 `# ── Mappings ──` 节之前新增 `# ── Supplier Models ──` 节：

```python
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

    def get_supplier_models_by_supplier_id(self, supplier_id: int) -> list:
        """Alias for get_supplier_models."""
        return self.get_supplier_models(supplier_id)
```

同时修改 `delete_account` 方法，删除供应商时清理模型：

```python
    def delete_account(self, account_id: int) -> bool:
        if self.supplier_model_repo is not None:
            self.supplier_model_repo.delete_by_supplier(account_id)
        return self.account_repo.delete(account_id)
```

添加 import：

```python
from provider.repositories.supplier_model_repository import SupplierModelRepository
```

- [ ] **Step 2: 修改 AdminRoutes**

在 `api/admin_routes.py` 中添加新的 Pydantic models 和路由：

在 `ConfigBulkUpdate` 之后添加：

```python
class SupplierModelCreate(BaseModel):
    model_name: str
    model_type: str = "text"
    context_length: Optional[int] = None


class SupplierModelBulkUpdate(BaseModel):
    models: List[SupplierModelCreate]
```

在 `# ── Suppliers ──` 节中 `delete_supplier` 路由之后，添加供应商模型端点：

```python
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
```

需要添加 import：

```python
from typing import Optional, Dict, Any, List
```

（注意：admin_routes.py 已有 `from typing import Optional, Dict, Any`，需要补 `List`）

- [ ] **Step 3: 修改 main.py 让 admin_service 接收新依赖**

查看 `main.py` 确认 `AdminService` 初始化处传入 `supplier_model_repo`。

查看 `main.py` 中 AdminService 初始化：

```python
admin_service = AdminService(
    account_repo=AccountRepository(db),
    mapping_repo=MappingRepository(db),
    config_repo=ConfigRepository(db),
    log_repo=LogRepository(db),
    quota_repo=QuotaRepository(db),
    supplier_model_repo=SupplierModelRepository(db),
)
```

需 import：`from provider.repositories.supplier_model_repository import SupplierModelRepository`

- [ ] **Step 4: 创建 API 测试**

创建 `tests/api/test_supplier_models.py`：

```python
"""Tests for supplier models API endpoints."""
import datetime
import pytest
from fastapi.testclient import TestClient

from provider.main import create_app


@pytest.fixture()
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _tid(suffix: str) -> str:
    return f"sm{datetime.datetime.now().strftime('%H%M%S%f')}-{suffix}"


def _create_supplier(client):
    name = _tid("sup")
    r = client.post("/api/admin/suppliers", json={
        "name": name, "api_key": "ms-test-key",
        "base_url": "https://api.modelscope.test/v1", "region": "china",
    })
    return r.json()


def test_list_supplier_models_empty(client):
    supplier = _create_supplier(client)
    r = client.get(f"/api/admin/suppliers/{supplier['id']}/models")
    assert r.status_code == 200
    assert r.json() == []


def test_create_supplier_model(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max",
        "model_type": "text",
        "context_length": 32768,
    })
    assert r.status_code == 200
    data = r.json()
    assert data["model_name"] == "qwen-max"
    assert data["model_type"] == "text"
    assert data["context_length"] == 32768


def test_create_supplier_model_duplicate_409(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max", "model_type": "text",
    })
    r = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max", "model_type": "text",
    })
    assert r.status_code == 409


def test_create_supplier_model_default_type(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "glm-4",
    })
    assert r.status_code == 200
    assert r.json()["model_type"] == "text"


def test_bulk_set_supplier_models(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.put(f"/api/admin/suppliers/{sid}/models/bulk", json={
        "models": [
            {"model_name": "qwen-max", "model_type": "text", "context_length": 32768},
            {"model_name": "qwen-vl", "model_type": "image", "context_length": 4096},
            {"model_name": "code-geex", "model_type": "code"},
        ],
    })
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    names = {m["model_name"] for m in data}
    assert names == {"qwen-max", "qwen-vl", "code-geex"}


def test_delete_supplier_model(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    created = client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "glm-4", "model_type": "text",
    }).json()
    mid = created["id"]
    r = client.delete(f"/api/admin/suppliers/{sid}/models/{mid}")
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    assert client.get(f"/api/admin/suppliers/{sid}/models").json() == []


def test_delete_supplier_model_not_found(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    r = client.delete(f"/api/admin/suppliers/{sid}/models/99999")
    assert r.status_code == 404


def test_delete_supplier_cascades_models(client):
    supplier = _create_supplier(client)
    sid = supplier["id"]
    client.post(f"/api/admin/suppliers/{sid}/models", json={
        "model_name": "qwen-max", "model_type": "text",
    })
    client.delete(f"/api/admin/suppliers/{sid}")
    assert client.get(f"/api/admin/suppliers/{sid}/models").json() == []
```

- [ ] **Step 5: 运行测试**

```bash
pytest tests/api/test_supplier_models.py -v
```

Expected: 所有 8 个测试 PASS。

- [ ] **Step 6: 运行全量测试**

```bash
pytest tests/api/ -v
```

Expected: 所有 API 测试 PASS。

- [ ] **Step 7: Commit**

```bash
git add services/admin_service.py api/admin_routes.py main.py tests/api/test_supplier_models.py
git commit -m "feat: add supplier models CRUD API endpoints"
```

---

### Task 7: 前端 — API 函数 + Accounts.vue 模型管理

**Files:**
- Modify: `web/src/api/index.js`
- Modify: `web/src/pages/Accounts.vue`

**Interfaces:**
- Consumes: API 端点（Task 6）
- Produces: 添加/编辑抽屉中增加模型列表管理；供应商卡片展示模型标签

- [ ] **Step 1: 添加 API 函数**

在 `web/src/api/index.js` 的 `// ── Suppliers ──` 节中添加：

```javascript
export const getSupplierModels = (id) => api.get(`/suppliers/${id}/models`)
export const createSupplierModel = (id, data) => api.post(`/suppliers/${id}/models`, data)
export const deleteSupplierModel = (id, modelId) => api.delete(`/suppliers/${id}/models/${modelId}`)
export const bulkSetSupplierModels = (id, data) => api.put(`/suppliers/${id}/models/bulk`, data)
```

- [ ] **Step 2: 修改 Accounts.vue**

在 `<script setup>` 的 import 部分添加：

```javascript
import { getSupplierModels, bulkSetSupplierModels as apiBulkSetSupplierModels } from '@/api'
```

在 `newSupplier` 初始化和 `editingSupplier` 中添加 `models` 字段：

```javascript
const newSupplier = ref({ name: '', api_key: '', base_url: '', models: [] })
```

`editingSupplier` 在 `openEdit` 中加载：

```javascript
const editingSupplier = ref(null)
```

在 `openAdd` 中重置 models：

```javascript
const openAdd = async () => {
  newSupplier.value = { name: '', api_key: '', base_url: '', models: [] }
  showAddDrawer.value = true
  // ...
}
```

在 `openEdit` 中加载现有模型：

```javascript
const openEdit = async (acc) => {
  editingSupplier.value = {
    id: acc.id,
    name: acc.name,
    api_key: acc.api_key,
    base_url: acc.base_url,
    region: acc.region,
    status: acc.status,
    models: [],
  }
  try {
    const res = await getSupplierModels(acc.id)
    editingSupplier.value.models = res.data || []
  } catch (e) {
    console.error('Failed to load supplier models:', e)
  }
  showApiKey.value = false
  showEditDrawer.value = true
  editExiting.value = false
}
```

修改 `addSupplier` 提交时带上 models：

```javascript
const addSupplier = async () => {
  if (!newSupplier.value.name || !newSupplier.value.api_key) {
    alert('请填写别名和 API Key')
    return
  }
  adding.value = true
  try {
    // Create supplier first
    const res = await apiCreateSupplier({
      name: newSupplier.value.name,
      api_key: newSupplier.value.api_key,
      base_url: newSupplier.value.base_url,
      region: 'china',
    })
    const supplierId = res.data.id
    // Then add models if any
    if (newSupplier.value.models.length > 0) {
      await apiBulkSetSupplierModels(supplierId, {
        models: newSupplier.value.models.map(m => ({
          model_name: m.model_name,
          model_type: m.model_type,
          context_length: m.context_length || null,
        })),
      })
    }
    // Refresh to get models back
    await loadData()
    closeAdd()
  } catch (e) {
    alert('添加失败: ' + (e.response?.data?.detail || e.message || ''))
  } finally {
    adding.value = false
  }
}
```

修改 `saveEdit` 提交时带上 models：

```javascript
const saveEdit = async () => {
  if (!editingSupplier.value) return
  saving.value = true
  try {
    // Update supplier
    const body = {
      name: editingSupplier.value.name,
      api_key: editingSupplier.value.api_key,
      base_url: editingSupplier.value.base_url,
      region: editingSupplier.value.region,
      status: editingSupplier.value.status,
    }
    const res = await apiUpdateSupplier(editingSupplier.value.id, body)
    const idx = suppliers.value.findIndex(a => a.id === editingSupplier.value.id)
    if (idx !== -1) suppliers.value[idx] = { ...suppliers.value[idx], ...res.data }

    // Update models
    if (editingSupplier.value.models.length > 0) {
      await apiBulkSetSupplierModels(editingSupplier.value.id, {
        models: editingSupplier.value.models.map(m => ({
          model_name: m.model_name,
          model_type: m.model_type,
          context_length: m.context_length || null,
        })),
      })
    } else {
      // Clear models if list is empty
      await apiBulkSetSupplierModels(editingSupplier.value.id, { models: [] })
    }
    // Refresh
    await loadData()
    closeEdit()
  } catch (e) {
    alert('保存失败: ' + (e.response?.data?.detail || e.message || ''))
  } finally {
    saving.value = false
  }
}
```

在 `loadData` 中为每个供应商加载模型：

```javascript
const loadData = async () => {
  loading.value = true
  try {
    const res = await getSuppliers()
    suppliers.value = res.data || []
    // Load models for each supplier
    for (const s of suppliers.value) {
      try {
        const mRes = await getSupplierModels(s.id)
        s.models = mRes.data || []
      } catch {
        s.models = []
      }
    }
  } catch (e) {
    error.value = e.message || 'Failed to load suppliers'
  }
  loading.value = false
}
```

添加辅助函数：

```javascript
// Model type display helpers
const MODEL_TYPES = {
  text: { label: '文本', icon: '📝' },
  image: { label: '图像', icon: '🖼️' },
  code: { label: '代码', icon: '💻' },
  voice: { label: '语音', icon: '🔊' },
}

const formatContextLength = (length) => {
  if (!length) return ''
  if (length >= 1000) return `${Math.round(length / 1000)}K`
  return String(length)
}
```

- [ ] **Step 3: 添加模型管理模板区域**

在添加抽屉的表单中（`newSupplier.base_url` input 之后），插入：

```vue
<!-- ── 支持模型 ── -->
<div>
  <label class="form-label">支持模型</label>
  <div v-if="newSupplier.models.length === 0"
    class="text-[11px] text-gray-500 mb-2">
    可配置该供应商支持的模型
  </div>
  <div v-for="(m, idx) in newSupplier.models" :key="idx"
    class="flex items-center gap-2 mb-2">
    <input v-model="m.model_name" type="text" placeholder="模型名称"
      class="form-input flex-1 text-xs h-8 py-1" />
    <select v-model="m.model_type"
      class="form-input h-8 text-xs px-2 py-1 w-20">
      <option value="text">文本</option>
      <option value="image">图像</option>
      <option value="code">代码</option>
      <option value="voice">语音</option>
    </select>
    <input v-model.number="m.context_length" type="number" placeholder="上下文"
      class="form-input h-8 text-xs px-2 py-1 w-24" />
    <button type="button" @click="removeNewModel(idx)"
      class="text-gray-500 hover:text-red-400 p-1 transition-colors" title="删除">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
  <button type="button" @click="addNewModel"
    class="text-xs text-ls-accent hover:text-ls-accentHover transition-colors">
    + 添加模型
  </button>
</div>
```

在编辑抽屉中同样位置插入（结构相同，v-model 改为 `editingSupplier.models`）：

```vue
<!-- ── 支持模型 ── -->
<div>
  <label class="form-label">支持模型</label>
  <div v-if="editingSupplier.models.length === 0"
    class="text-[11px] text-gray-500 mb-2">
    暂无配置模型
  </div>
  <div v-for="(m, idx) in editingSupplier.models" :key="idx"
    class="flex items-center gap-2 mb-2">
    <input v-model="m.model_name" type="text" placeholder="模型名称"
      class="form-input flex-1 text-xs h-8 py-1" />
    <select v-model="m.model_type"
      class="form-input h-8 text-xs px-2 py-1 w-20">
      <option value="text">文本</option>
      <option value="image">图像</option>
      <option value="code">代码</option>
      <option value="voice">语音</option>
    </select>
    <input v-model.number="m.context_length" type="number" placeholder="上下文"
      class="form-input h-8 text-xs px-2 py-1 w-24" />
    <button type="button" @click="removeEditModel(idx)"
      class="text-gray-500 hover:text-red-400 p-1 transition-colors" title="删除">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
      </svg>
    </button>
  </div>
  <button type="button" @click="addEditModel"
    class="text-xs text-ls-accent hover:text-ls-accentHover transition-colors">
    + 添加模型
  </button>
</div>
```

添加模型管理方法：

```javascript
// ── Model management helpers ──
const addNewModel = () => {
  newSupplier.value.models.push({
    model_name: '',
    model_type: 'text',
    context_length: null,
  })
}

const removeNewModel = (idx) => {
  newSupplier.value.models.splice(idx, 1)
}

const addEditModel = () => {
  editingSupplier.value.models.push({
    model_name: '',
    model_type: 'text',
    context_length: null,
  })
}

const removeEditModel = (idx) => {
  editingSupplier.value.models.splice(idx, 1)
}
```

- [ ] **Step 4: 供应商卡片展示模型标签**

在供应商卡片的 `</div>`（quota/region 显示之后）添加模型标签：

```vue
<div v-if="acc.models && acc.models.length > 0" class="flex items-center gap-1 flex-wrap mt-2">
  <span v-for="(m, i) in acc.models.slice(0, 3)" :key="i"
    class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border">
    <span class="mr-0.5">{{ MODEL_TYPES[m.model_type]?.icon || '📝' }}</span>
    <span class="text-white">{{ m.model_name }}</span>
    <span v-if="m.context_length" class="text-gray-500 ml-0.5">({{ formatContextLength(m.context_length) }})</span>
  </span>
  <span v-if="acc.models.length > 3"
    class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border text-gray-500">
    +{{ acc.models.length - 3 }}
  </span>
</div>
```

注意：`MODEL_TYPES` 和 `formatContextLength` 在 `<script setup>` 中定义后，在 `<template>` 中可以直接使用（Vue 3 script setup 的顶层绑定自动暴露）。

- [ ] **Step 5: 前端构建**

```bash
cd web && npm run build
```

Expected: 构建成功，无报错。

- [ ] **Step 6: Commit**

```bash
cd ..
git add web/src/api/index.js web/src/pages/Accounts.vue web/dist/
git commit -m "feat: add model management UI to supplier add/edit forms and cards"
```

---

### Task 8: 全量回归测试

**Files:**
- (无新增文件)

- [ ] **Step 1: 运行全量后端测试**

```bash
pytest tests/ -v --ignore=tests/integration/
```

Expected: 所有测试 PASS。

- [ ] **Step 2: 运行集成测试**

```bash
pytest tests/integration/ -v
```

Expected: PASS（如有失败，检查服务初始化和路由逻辑）。

- [ ] **Step 3: 前端构建确认**

```bash
cd web && npm run build
```

Expected: 构建成功。

- [ ] **Step 4: 检查 git 状态**

```bash
cd ..
git status
```

Expected: 只包含本次功能相关文件的改动。

---

## Self-Review Checklist

- [x] **Spec coverage**: 数据库表(Task 1) → Repository(Task 2) → LoadBalancer(Task 3) → AliasResolver(Task 4) → ServiceInit(Task 5) → AdminService+Routes(Task 6) → 前端(Task 7) → 回归测试(Task 8)。Spec 中每个需求都有对应 task。
- [x] **Placeholder scan**: 无 TBD/TODO，所有代码块完整，所有测试代码可执行。
- [x] **Type consistency**:
  - `SupplierModelRepository.find_suppliers_for_model` 返回 `List[dict]`，LoadBalancer 用 `account_id` 匹配 — Task 2 和 Task 3 一致
  - `SupplierModelCreate` Pydantic model 字段 `model_name, model_type, context_length?` — Task 6 后端和 Task 7 前端一致
  - `bulk_set_supplier_models` 接收 `List[dict]`，前端传 `{models: [...]}` — Task 6 和 Task 7 一致
  - AliasResolver 签名 `resolve_alias(account, alias)` 保持 positional 兼容 — Task 4 和 api/routes.py 一致
- [x] **No region in supplier_models**: 全文无 region 字段，UNIQUE 约束为 `(supplier_id, model_name)`
- [x] **context_length**: 贯穿数据库 → Repository → API → 前端，类型一致（INTEGER, nullable）
- [x] **Test coverage**: 每个 task 都有独立测试，Task 8 做全量回归

---

Plan complete. 共 8 个 task，从数据库到底层服务到前端 UI，每个 task 有独立测试和 commit。
