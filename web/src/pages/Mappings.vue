<template>
  <div>
    <PageHeader title="模型映射" subtitle="管理模型别名与实际模型 ID 的映射关系">
      <template #action>
        <button @click="openAdd" class="btn btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          添加映射
        </button>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">Error: {{ error }}</div>
      <div v-else>
      <div class="space-y-3">
        <!-- Mapping rows -->
        <div v-for="m in mappings" :key="m.alias_name"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-gray-700 transition-all">
          <div class="flex items-center gap-6">
            <div>
              <p class="text-xs text-gray-500 mb-0.5">别名</p>
              <p class="text-sm font-mono text-ls-accent font-semibold">{{ m.alias_name }}</p>
            </div>
            <div class="flex items-center gap-2 text-gray-600">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </div>
            <div>
              <p class="text-xs text-gray-500 mb-0.5">实际模型 ID</p>
              <p class="text-sm font-mono text-white">{{ m.actual_model_id }}</p>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <span class="inline-flex items-center rounded-md px-1.5 py-0.5 bg-green-500/10 text-green-400 text-xs">活跃</span>
            <button @click="openEdit(m)" class="text-gray-500 hover:text-white p-1 transition-colors" title="编辑">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button @click="openDeleteConfirm(m)" class="text-gray-500 hover:text-red-400 p-1 transition-colors" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>

        <!-- Empty state -->
        <div v-if="mappings.length === 0"
          class="bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-12 flex flex-col items-center justify-center gap-3">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-600">
            <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
          <p class="text-sm text-gray-500">暂无映射规则</p>
          <button @click="openAdd" class="text-xs text-ls-accent hover:text-ls-accentHover">添加第一个映射 →</button>
        </div>
      </div>

      <div class="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
        共 {{ mappings.length }} 条映射
      </div>
      </div>
    </div>

    <!-- ── 添加/编辑 映射 抽屉 ── -->
    <Drawer v-model="showFormDrawer" :title="isEditing ? '编辑映射' : '添加映射'">
      <div class="space-y-4">
        <div>
          <label class="form-label">别名</label>
          <input v-model="form.alias" type="text" placeholder="my-alias"
            class="form-input font-mono" :disabled="isEditing"
            @keyup.enter="submitForm" ref="formAliasInput">
          <p v-if="isEditing" class="text-[10px] text-gray-600 mt-1">别名不可修改</p>
        </div>
        <div v-if="isEditing && currentMapping?.bound_models?.length > 0" class="mb-3">
          <label class="form-label">绑定模型</label>
          <div class="tag-list">
            <div v-for="model in currentMapping.bound_models" :key="model.id" class="tag-item">
              <span>{{ model.supplier_name || `供应商${model.supplier_id}` }} {{ model.model_name }}</span>
              <button @click="removeMappingModel(model.id)" class="tag-delete">×</button>
            </div>
          </div>
        </div>
        <div v-else class="text-xs text-gray-500 mb-3">
          多模型支持: 添加/删除模型将显示在此处
        </div>
      </div>
      <template #footer>
        <button @click="closeForm" class="btn btn-secondary btn-esc">取消</button>
        <button @click="openSelector" class="btn btn-secondary">管理绑定模型</button>
        <button @click="submitForm" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? '保存中...' : isEditing ? '保存' : '添加' }}
        </button>
      </template>
    </Drawer>

    <!-- ── 模型选择器 抽屉 ── -->
    <Drawer v-model="showSelectorDrawer" title="管理绑定模型">
      <div class="space-y-4">
        <MappingModelSelector v-model="currentMapping.bound_models" />
      </div>
      <template #footer>
        <button @click="closeSelector" class="btn btn-secondary btn-esc">取消</button>
        <button @click="closeSelector" class="btn btn-primary">完成</button>
      </template>
    </Drawer>

    <!-- ── 删除确认 弹窗 ── -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定删除别名 <strong class='text-white'>${deletingItem?.alias_name || ''}</strong> 的映射吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, nextTick, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import MappingModelSelector from '@/components/MappingModelSelector.vue'
import { getMappings, bulkUpdateMappings as apiBulkUpdate, deleteMapping as apiDelete, getMappingModels, removeMappingModel as apiRemoveMappingModel } from '@/api'

const toast = inject('$toast')

const loading = ref(true)
const error = ref(null)
const mappings = ref([])
const currentMapping = ref(null)

// ── Form drawer ──
const showFormDrawer = ref(false)
const submitting = ref(false)
const formAliasInput = ref(null)
const isEditing = ref(false)
const form = ref({ alias: '', model_id: '' })

// ── Model selector drawer ──
const showSelectorDrawer = ref(false)

// ── Delete modal ──
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingItem = ref(null)

// ── Data loading ──
const loadData = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await getMappings()
    mappings.value = res.data || []
    // Load models for each mapping
    for (const m of mappings.value) {
      await loadMappingModels(m.alias_name)
    }
  } catch (e) {
    error.value = e.message || 'Failed to load mappings'
  }
  loading.value = false
}

const loadMappingModels = async (aliasName) => {
  try {
    const res = await getMappingModels(aliasName)
    const mapping = mappings.value.find(m => m.alias_name === aliasName)
    if (mapping) {
      mapping.bound_models = res.data || []
    }
  } catch (e) {
    console.error('Failed to load mapping models:', e)
  }
}

// ── Form ──
const openAdd = async () => {
  isEditing.value = false
  form.value = { alias: '', model_id: '' }
  showFormDrawer.value = true
  await nextTick()
  formAliasInput.value?.focus()
}

const openEdit = async (item) => {
  isEditing.value = true
  currentMapping.value = item
  try {
    const res = await getMappingModels(item.alias_name)
    currentMapping.value.bound_models = res.data || []
  } catch (e) {
    console.error('Failed to load mapping models:', e)
  }
  showFormDrawer.value = true
}

const closeForm = () => {
  showFormDrawer.value = false
  currentMapping.value = null
}

const openSelector = () => {
  showSelectorDrawer.value = true
}

const closeSelector = () => {
  showSelectorDrawer.value = false
}

const removeMappingModel = async (modelId) => {
  try {
    await apiRemoveMappingModel(modelId)
    await loadMappingModels(currentMapping.value.alias_name)
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  }
}

const submitForm = async () => {
  if (!form.value.alias || !form.value.model_id) {
    toast('请填写别名和实际模型 ID', 'error')
    return
  }
  submitting.value = true
  try {
    // Build full mappings dict (all existing + this one)
    const allMappings = {}
    for (const m of mappings.value) {
      allMappings[m.alias_name] = m.actual_model_id
    }
    allMappings[form.value.alias] = form.value.model_id

    await apiBulkUpdate(allMappings)
    await loadData()
    closeForm()
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    submitting.value = false
  }
}

// ── Delete ──
const openDeleteConfirm = (item) => {
  deletingItem.value = item
  showDeleteModal.value = true
}

const closeDeleteConfirm = () => {
  showDeleteModal.value = false
  deletingItem.value = null
}

const confirmDelete = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await apiDelete(deletingItem.value.alias_name)
    await loadData()
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  } finally {
    deleting.value = false
  }
}

const handleKeyDown = (e) => {
  if (e.key === 'Escape') {
    if (showSelectorDrawer.value) {
      closeSelector()
    } else if (showDeleteModal.value) {
      closeDeleteConfirm()
    } else if (showFormDrawer.value) {
      closeForm()
    }
  }
  if (e.key === 'Enter' && showDeleteModal.value) {
    confirmDelete()
  }
}

onMounted(() => {
  loadData()
  document.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.tag-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.tag-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.5rem 0.75rem;
  background: var(--ls-bg);
  border: 1px solid var(--ls-border);
  border-radius: 6px;
  font-size: 0.875rem;
}

.tag-delete {
  background: none;
  border: none;
  color: var(--text-400);
  cursor: pointer;
  padding: 0.25rem;
  font-size: 1.25rem;
  line-height: 1;
}

.tag-delete:hover {
  color: var(--text-200);
}
</style>
