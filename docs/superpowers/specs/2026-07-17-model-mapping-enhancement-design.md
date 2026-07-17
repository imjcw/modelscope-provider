# Model Mapping Enhancement Design

## Overview

Enhance the model mapping page to support multiple supplier models per mapping alias. When a user requests via an alias, the system will:
1. First check if the alias has mapping definitions
2. If yes, select one model from the bound suppliers using existing load balancer strategy
3. If no mapping exists, fall back to the original behavior of querying suppliers directly

## Current Architecture

### Database Schema
- `model_mappings`: `alias_name` (UNIQUE) → `actual_model_id` (single value)
- `supplier_models`: `supplier_id` → `model_name` (supports multiple suppliers per model)

### Backend Components
- `MappingRepository`: Manages `model_mappings` table
- `ModelAliasResolver`: Resolves alias to actual model ID (prioritizes local mapping table)
- `LoadBalancer`: Round-robin load balancing for account selection
- `SupplierModelRepository`: Finds suppliers that support a given model

### Frontend
- `Mappings.vue`: Lists all mappings with simple alias → model_id mapping
- `admin_routes.py`: API endpoints for mapping CRUD operations

## Problem Statement

Currently, each mapping alias can only bind to a single `actual_model_id`. This doesn't support scenarios where you want to:
- Create a unified alias (e.g., "gpt-4") that routes to different actual models from different suppliers
- Implement vendor selection or load balancing within the alias
- Maintain flexibility while presenting a unified API to users

## Requirements

### Functional Requirements
1. **Multi-model support per alias**: A mapping alias can bind multiple supplier models
2. **Tag-based UI**: Display bound models as tags in a list format
3. **Model selection**: Add a dropdown to select supplier and model when creating/editing mappings
4. **Load balancing**: When multiple models are bound to an alias, use existing load balancer strategy to select one
5. **Fallback behavior**: If no mapping exists for a requested alias, fall back to original behavior

### Non-Functional Requirements
- Maintain existing `model_mappings` table for backward compatibility
- Preserve round-robin load balancing for multi-model aliases
- Ensure no performance degradation with the new feature
- Keep the UI consistent with existing supplier management interface

## Design

### 1. Database Schema

#### New Table: `mapping_models`

```sql
CREATE TABLE IF NOT EXISTS mapping_models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_name TEXT NOT NULL,
    supplier_id INTEGER NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (alias_name) REFERENCES model_mappings(alias_name) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES accounts(id) ON DELETE CASCADE,
    UNIQUE(alias_name, supplier_id, model_name)
);

CREATE INDEX IF NOT EXISTS idx_mapping_models_alias ON mapping_models(alias_name);
CREATE INDEX IF NOT EXISTS idx_mapping_models_supplier ON mapping_models(supplier_id);
```

**Rationale:**
- `alias_name` links to `model_mappings.alias_name` (CASCADE delete removes associated mapping models)
- `supplier_id` links to `accounts.id` (CASCADE delete removes orphaned mapping models)
- `id` enables individual model management (add/remove specific models)

### 2. Backend Components

#### 2.1 MappingModelRepository

**File**: `repositories/mapping_model_repository.py`

```python
import logging
from typing import List, Optional
from provider.core.database import DatabaseManager

logger = logging.getLogger(__name__)


class MappingModelRepository:
    """Repository for mapping_models table (alias -> multiple supplier models)."""

    def __init__(self, db: DatabaseManager):
        self.db = db

    def find_by_alias(self, alias_name: str) -> List[dict]:
        """Get all supplier models bound to a mapping alias."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM mapping_models WHERE alias_name = ? ORDER BY id",
                (alias_name,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def add_model(self, alias_name: str, supplier_id: int, model_name: str) -> dict:
        """Add a supplier model to a mapping alias. Raises on UNIQUE conflict."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO mapping_models (alias_name, supplier_id, model_name)
                   VALUES (?, ?, ?)""",
                (alias_name, supplier_id, model_name),
            )
            cursor = conn.execute(
                "SELECT * FROM mapping_models WHERE alias_name = ? AND id = last_insert_rowid()",
                (alias_name,),
            )
            row = cursor.fetchone()
            result = dict(row)
            logger.info(
                f"Added mapping model: alias={alias_name}, supplier_id={supplier_id}, model={model_name}"
            )
            return result

    def remove_model(self, model_id: int) -> bool:
        """Remove a mapping model by its row id."""
        with self.db.get_connection() as conn:
            cursor = conn.execute("DELETE FROM mapping_models WHERE id = ?", (model_id,))
            return cursor.rowcount > 0

    def get_by_supplier(self, supplier_id: int) -> List[dict]:
        """Get all mapping models for a specific supplier."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM mapping_models WHERE supplier_id = ? ORDER BY alias_name",
                (supplier_id,),
            )
            return [dict(row) for row in cursor.fetchall()]
```

#### 2.2 Enhanced AdminService

**File**: `services/admin_service.py`

Add method to handle multi-model mapping resolution:

```python
def resolve_mapping_alias(self, alias: str) -> str:
    """Resolve mapping alias to actual model ID with multi-model support.

    Returns:
        actual_model_id: The selected model name from bound suppliers

    Raises:
        ValueError: If no models are bound to this alias
    """
    if self.mapping_model_repo is None:
        raise ValueError("Mapping model repo not configured")

    # Fetch all models bound to this alias
    model_entries = self.mapping_model_repo.find_by_alias(alias)

    if not model_entries:
        raise ValueError(f"No models bound to alias '{alias}'")

    # Build a list of accounts for load balancing
    accounts_for_alias = []
    for entry in model_entries:
        accounts_for_alias.append(
            type('Account', (), {
                'account_id': f'mapping_{entry["id"]}',
                'base_url': '',  # Will be filled below
                'model_name': entry['model_name'],
                'actual_model_id': entry['model_name'],
                'current_index': 0,
            })()
        )

    # Fetch supplier details for all suppliers in the mapping
    supplier_ids = {entry['supplier_id'] for entry in model_entries}
    supplier_details = {}
    for sid in supplier_ids:
        sup = self.account_repo.find_by_id(sid)
        if sup:
            supplier_details[sid] = sup

    if not supplier_details:
        raise ValueError(f"Cannot find supplier details for alias '{alias}'")

    # Use the first supplier's base_url for all accounts (they're the same supplier)
    base_url = next(iter(supplier_details.values()))['base_url']

    # Override base_url for all accounts
    for acc in accounts_for_alias:
        acc.base_url = base_url

    # Select account using load balancer
    from provider.services.load_balancer import LoadBalancer
    load_balancer = LoadBalancer(accounts_for_alias)
    selected = load_balancer.select_account(model_name=model_entries[0]['model_name'])

    return selected.actual_model_id
```

**Note**: This method is added to `AdminService` because it needs access to both `mapping_model_repo` and `account_repo`. The existing `ModelAliasResolver` will continue to use its fallback HTTP method for single-model mappings.

#### 2.3 Service Layer Updates

**File**: `services/admin_service.py`

Add methods:

```python
# Add to AdminService.__init__()
def __init__(self, account_repo, mapping_repo, config_repo, log_repo,
             quota_repo=None, supplier_model_repo=None, mapping_model_repo=None):
    # ... existing ...
    self.mapping_model_repo = mapping_model_repo

# New methods
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

def get_all_suppliers(self):
    """Get all suppliers for model selection dropdown."""
    return self.account_repo.find_all()
```

#### 2.4 API Routes

**File**: `api/admin_routes.py`

Add new routes:

```python
# ── Mapping Models ──

@router.get("/mappings/{alias_name}/models")
def list_mapping_models(alias_name: str, service=Depends(get_admin_service)):
    """Get all models bound to a mapping alias."""
    return service.get_mapping_models(alias_name)

@router.post("/mappings/{alias_name}/models")
def add_mapping_model(
    alias_name: str,
    body: MappingModelCreate,
    service=Depends(get_admin_service)
):
    """Add a model to a mapping alias."""
    try:
        return service.add_mapping_model(
            alias_name,
            supplier_id=body.supplier_id,
            model_name=body.model_name,
        )
    except Exception as e:
        if "UNIQUE constraint" in str(e):
            raise HTTPException(status_code=409, detail=f"Model {body.model_name} already bound to this alias")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/mappings/models/{model_id}")
def remove_mapping_model(model_id: int, service=Depends(get_admin_service)):
    """Remove a model from a mapping alias."""
    if not service.remove_mapping_model(model_id):
        raise HTTPException(status_code=404, detail="Mapping model not found")
    return {"ok": True}

@router.get("/suppliers")
def list_suppliers(service=Depends(get_admin_service)):
    """Get all suppliers for model selection."""
    return service.get_all_suppliers()

# ── Mapping Resolution ──

@router.get("/mappings/resolve/{alias_name}")
def resolve_mapping_alias(alias_name: str, service=Depends(get_admin_service)):
    """Resolve mapping alias to actual model ID (for multi-model support)."""
    try:
        actual_model_id = service.resolve_mapping_alias(alias_name)
        return {"alias": alias_name, "actual_model_id": actual_model_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
```

Add request model:

```python
class MappingModelCreate(BaseModel):
    supplier_id: int = Field(..., description="Supplier ID")
    model_name: str = Field(..., description="Model name on supplier")
```

### 3. Frontend Components

#### 3.1 API Layer

**File**: `web/src/api.js` (or equivalent)

Add functions:

```javascript
export function getMappingModels(aliasName) {
  return request.get(`/admin/mappings/${aliasName}/models`)
}

export function addMappingModel(aliasName, data) {
  return request.post(`/admin/mappings/${aliasName}/models`, data)
}

export function removeMappingModel(modelId) {
  return request.delete(`/admin/mappings/models/${modelId}`)
}

export function getAllSuppliers() {
  return request.get('/admin/suppliers')
}
```

#### 3.2 Mappings.vue Refactor

**New UI Layout:**

```
┌─────────────────────────────────────────────────────────────┐
│ 映射别名: my-gpt-4              [编辑] [删除]                │
│ 实际模型ID: gpt-4-turbo                                [★]   │
│                                                           │
│ 绑定的模型（标签列表）：                                  │
│   [阿里云] qwen-max         [删除]                        │
│   [腾讯云] deepseek-chat    [删除]                        │
│   [百度]      ernie-bot      [删除]                        │
└─────────────────────────────────────────────────────────────┘
```

**Add/Edit Modal:**

```
┌─────────────────────────────────────────────────────────────┐
│ 别名: my-gpt-4                                  (不可修改)  │
│                                                           │
│ 实际模型ID: gpt-4-turbo                               [★]   │
│                                                           │
│ 绑定模型（可多选）：                                      │
│   ┌─────────────────────────────────────────────────┐   │
│   │ 选择供应商: [阿里云 ▼]                           │   │
│   │   - qwen-max                                   │   │
│   │   - qwen-plus                                  │   │
│   │   - qwen-turbo                                 │   │
│   └─────────────────────────────────────────────────┘   │
│                                                           │
│   ☐ 阿里云 qwen-max   [x]                               │
│   ☐ 腾讯云 deepseek-chat [x]                             │
│   [+ 添加模型...]                                        │
└─────────────────────────────────────────────────────────────┘
```

**Implementation approach:**
1. Replace simple `actual_model_id` input with a read-only display (shows only when single model)
2. Replace text with a list of tags
3. Add "添加模型" button that opens a selector drawer
4. Implement tag deletion
5. Auto-populate model list when opening "添加模型" drawer

**Tag list display:**
```vue
<div v-for="model in boundModels" :key="model.id" class="tag-item">
  <span class="tag-name">{{ model.model_name }}</span>
  <span class="tag-supplier">{{ model.supplier_name }}</span>
  <button @click="removeModel(model.id)" class="tag-delete">×</button>
</div>
```

#### 3.3 Model Selector Component

**File**: `web/src/components/MappingModelSelector.vue` (new)

**Features:**
- Supplier dropdown
- Model dropdown (populated based on selected supplier)
- "添加" button
- List of selected models with delete buttons

```vue
<template>
  <div class="mapping-model-selector">
    <label class="form-label">绑定模型</label>

    <!-- Supplier selection -->
    <div class="mb-3">
      <label class="form-label">供应商</label>
      <CSelect v-model="selectedSupplier" :options="supplierOptions" placeholder="选择供应商" />
    </div>

    <!-- Model selection -->
    <div class="mb-3">
      <label class="form-label">模型</label>
      <CSelect v-model="selectedModel" :options="modelOptions" placeholder="选择模型" />
    </div>

    <!-- Add button -->
    <button @click="addModel" class="btn btn-secondary w-full">
      添加模型
    </button>

    <!-- Selected models list -->
    <div v-if="selectedModels.length > 0" class="mt-3">
      <label class="form-label">已选择的模型</label>
      <div class="tag-list">
        <div v-for="model in selectedModels" :key="model.id" class="tag-item">
          <span>{{ model.supplier_name }} {{ model.model_name }}</span>
          <button @click="removeModel(model.id)" class="tag-delete">×</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { getAllSuppliers } from '@/api'

const props = defineProps(['modelList'])
const emit = defineEmits(['update:modelList'])

const suppliers = ref([])
const selectedSupplier = ref(null)
const selectedModel = ref(null)

const selectedModels = computed({
  get: () => props.modelList,
  set: (val) => emit('update:modelList', val)
})

const supplierOptions = computed(() =>
  suppliers.value.map(s => ({ label: s.name, value: s.id }))
)

const modelOptions = computed(() => {
  if (!selectedSupplier.value) return []
  const supplier = suppliers.value.find(s => s.id === selectedSupplier.value)
  if (!supplier?.models) return []
  return supplier.models.map(m => ({
    label: m.model_name,
    value: m.model_name
  }))
})

const loadSuppliers = async () => {
  const res = await getAllSuppliers()
  suppliers.value = res.data || []
}

const addModel = () => {
  if (!selectedSupplier.value || !selectedModel.value) {
    alert('请选择供应商和模型')
    return
  }

  // Check if already added
  const exists = selectedModels.value.some(
    m => m.supplier_id === selectedSupplier.value && m.model_name === selectedModel.value
  )
  if (exists) {
    alert('该模型已添加')
    return
  }

  selectedModels.value.push({
    id: Date.now(),
    supplier_id: selectedSupplier.value,
    model_name: selectedModel.value,
    supplier_name: suppliers.value.find(s => s.id === selectedSupplier.value)?.name
  })

  selectedModel.value = null
}

const removeModel = (modelId) => {
  selectedModels.value = selectedModels.value.filter(m => m.id !== modelId)
}

onMounted(loadSuppliers)
</script>
```

## Implementation Plan

### Phase 1: Database & Backend Core
1. Update `DatabaseManager.initialize_tables()` to create `mapping_models` table
2. Create `repositories/mapping_model_repository.py`
3. Update `services/admin_service.py` to add new methods
4. Update `api/admin_routes.py` to add new routes
5. Update `models/alias_resolver.py` to support multi-model selection

### Phase 2: Frontend API Layer
1. Add API functions to `web/src/api.js`
2. Create `MappingModelSelector.vue` component

### Phase 3: Frontend UI
1. Refactor `Mappings.vue` to display tag list
2. Implement add/edit modal with model selector
3. Add model deletion functionality
4. Add keyboard shortcuts (ESC/Enter)

### Phase 4: Testing & Integration
1. Test multi-model mapping creation
2. Test round-robin load balancing
3. Test fallback behavior when no mapping exists
4. Test API integration
5. Test UI responsiveness

## Backward Compatibility

- Existing `model_mappings` entries remain valid (single model per alias)
- Migration path: Users can keep existing single-model mappings
- Load balancer behavior unchanged for multi-model aliases
- Fallback behavior preserved for aliases without mappings

## Edge Cases & Error Handling

1. **Multiple suppliers bound to same alias**: Load balancer will round-robin across them
2. **Model not available on supplier**: Still allowed (fallback to HTTP if needed)
3. **Supplier deleted**: Associated mapping models will be CASCADE deleted
4. **Alias deleted**: Associated mapping models will be CASCADE deleted
5. **Empty mapping model list**: Treat as no mapping (fallback to HTTP)

## Testing Strategy

### Backend Tests
1. Unit test `MappingModelRepository` CRUD operations
2. Integration test `ModelAliasResolver` with multi-model mapping
3. Test load balancer selection with mapping models

### Frontend Tests
1. Test model selector UI interaction
2. Test tag addition/deletion
3. Test form validation

### Manual Testing
1. Create mapping with 2+ supplier models
2. Send API request via alias
3. Verify load balancing occurs
4. Test fallback behavior
5. Test UI in different scenarios

## Success Criteria

1. ✅ A mapping alias can bind multiple supplier models
2. ✅ Tag-based UI displays bound models clearly
3. ✅ Load balancer selects models from bound suppliers
4. ✅ Fallback behavior works when no mapping exists
5. ✅ All CRUD operations work as expected
6. ✅ No regression in existing functionality

## Open Questions

1. **Model name conflict**: What if two suppliers have models with the same name (e.g., "gpt-4")?
   - **Decision**: Keep as-is; rely on supplier_id for uniqueness in display
   - **Alternative**: Append supplier name to make it unique (not chosen for simplicity)

2. **Editing alias name**: After creating a mapping, can the alias name be changed?
   - **Decision**: No, for data integrity (similar to existing behavior)
   - **Rationale**: Breaking changes could affect active requests

3. **Model versioning**: How to handle model updates on suppliers?
   - **Decision**: Users manually update mappings when model names change
   - **Alternative**: Auto-refresh from ModelScope API (not chosen for complexity)

## Future Enhancements

1. **Priority-based selection**: Allow users to set priority for each supplier model
2. **Geo-location routing**: Route to models closest to users
3. **Health checks**: Automatically mark unhealthy suppliers/Models as unavailable
4. **Analytics**: Track model selection statistics per alias
5. **Bulk import/export**: Import/export mapping configurations as JSON

---

**Document Version**: 1.0
**Created**: 2026-07-17
**Author**: ZCode Brainstorming Session
