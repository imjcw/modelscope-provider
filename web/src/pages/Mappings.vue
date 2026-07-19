<template>
  <div>
    <PageHeader title="虚拟模型" subtitle="管理虚拟模型ID及其绑定的供应商模型">
      <template #action>
        <div class="flex items-center gap-3">
          <ViewToggle v-model="viewMode" />
          <button @click="openAdd" class="btn btn-primary">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            添加虚拟模型
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">Error: {{ error }}</div>
      <div v-else>

      <!-- ═══════════════════════════════════════════
           视图 1：卡片行（默认）
           ═══════════════════════════════════════════ -->
      <div v-if="viewMode === 'row'" class="space-y-3">
        <div v-for="m in mappings" :key="m.alias_name"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-gray-700 transition-all">
          <div class="flex items-center gap-6">
            <div>
              <p class="text-xs text-gray-500 mb-0.5">虚拟模型ID</p>
              <p class="text-sm font-mono text-ls-accent font-semibold">{{ m.alias_name }}</p>
            </div>
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
          </div>
          <div class="flex items-center gap-2">
            <span class="status-badge-active">活跃</span>
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
      </div>

      <!-- ═══════════════════════════════════════════
           视图 2：网格卡片
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5">
        <div v-for="m in mappings" :key="m.alias_name"
          class="bg-ls-card rounded-lg border border-ls-border p-5 hover:border-gray-700 transition-all flex flex-col gap-3">
          <div class="flex items-center justify-between">
            <span class="status-badge-active">活跃</span>
            <div class="flex items-center gap-1">
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

          <div>
            <p class="text-xs text-gray-500 mb-0.5">虚拟模型ID</p>
            <p class="text-sm font-mono text-ls-accent font-semibold">{{ m.alias_name }}</p>
          </div>

          <div v-if="m.bound_models?.length" class="text-xs text-gray-500 pt-2 border-t border-ls-border">
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
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 3：表格
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'table'" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border text-xs">
              <th class="text-left px-5 py-3 font-medium">虚拟模型ID</th>
              <th class="text-left px-5 py-3 font-medium">绑定模型</th>
              <th class="text-left px-5 py-3 font-medium">状态</th>
              <th class="text-right px-5 py-3 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in mappings" :key="m.alias_name"
              class="border-b border-ls-border/50 hover:bg-ls-elevated/30 transition-colors">
              <td class="px-5 py-3 font-mono text-ls-accent font-semibold">{{ m.alias_name }}</td>
              <td class="px-5 py-3 text-xs text-gray-400">
                <button v-if="m.bound_models?.length" @click="toggleExpand(m.alias_name)" class="text-xs text-gray-400 hover:text-ls-accent flex items-center gap-1">
                  <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                    :class="expandedAlias === m.alias_name ? 'rotate-90' : ''" class="transition-transform">
                    <polyline points="9 18 15 12 9 6"/>
                  </svg>
                  绑定 {{ m.bound_models.length }} 个模型
                </button>
                <span v-else>0 个</span>
                <div v-if="expandedAlias === m.alias_name" class="mt-2 pl-3 border-l border-ls-border space-y-1">
                  <div v-for="b in m.bound_models" :key="b.id" class="flex items-center justify-between text-xs">
                    <span class="text-gray-300">{{ b.supplier_name || `供应商${b.supplier_id}` }} / {{ b.model_name }}</span>
                    <button @click.stop="removeBinding(m.alias_name, b.id)" class="text-gray-500 hover:text-red-400 ml-2">×</button>
                  </div>
                </div>
              </td>
              <td class="px-5 py-3">
                <span class="status-badge-active">活跃</span>
              </td>
              <td class="px-5 py-3">
                <div class="flex items-center justify-end gap-1">
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
              </td>
            </tr>
            <tr v-if="mappings.length === 0">
              <td colspan="4" class="px-5 py-8 text-center text-gray-500">暂无虚拟模型</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- ── 空态 + 底部统计 ── -->
      <div v-if="mappings.length === 0" class="mt-6 bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-12 flex flex-col items-center justify-center gap-3">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-600">
          <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
          <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
        </svg>
        <p class="text-sm text-gray-500">暂无虚拟模型</p>
        <button @click="openAdd" class="text-xs text-ls-accent hover:text-ls-accentHover">添加第一个虚拟模型 →</button>
      </div>
      <div v-else class="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
        共 {{ mappings.length }} 个虚拟模型
      </div>
      </div>
    </div>

    <!-- ── 添加/编辑 虚拟模型 抽屉 ── -->
    <Drawer v-model="showFormDrawer" :title="isEditing ? '编辑虚拟模型' : '添加虚拟模型'">
      <div class="space-y-4">
        <div>
          <label class="form-label">虚拟模型ID</label>
          <input v-model="form.alias" type="text" placeholder="my-virtual-model"
            class="form-input font-mono" :disabled="isEditing"
            @keyup.enter="submitForm" ref="formAliasInput">
          <p v-if="isEditing" class="text-[10px] text-gray-600 mt-1">虚拟模型ID不可修改</p>
        </div>
      </div>
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
            <button @click="removeBinding(formAlias, b.id)" class="tag-delete">×</button>
          </div>
        </div>
        <p v-else class="text-xs text-gray-500">暂无绑定模型，请求时将直接使用虚拟模型ID</p>
      </div>
      <template #footer>
        <button @click="closeForm" class="btn btn-secondary btn-esc">取消</button>
        <button @click="submitForm" class="btn btn-primary" :disabled="submitting">
          {{ submitting ? '保存中...' : isEditing ? '保存' : '添加' }}
        </button>
      </template>
    </Drawer>

    <!-- ── 删除确认 弹窗 ── -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定删除虚拟模型ID <strong class='text-white'>${deletingItem?.alias_name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import CSelect from '@/components/CSelect.vue'
import { getSuppliers, getMappings, bulkUpdateMappings as apiBulkUpdate, deleteMapping as apiDelete, getMappingModels, addMappingModel, removeMappingModel as apiRemoveMappingModel } from '@/api'
import ViewToggle from '@/components/ViewToggle.vue'
import { useViewPreference } from '@/composables/useViewPreference'

const toast = inject('$toast')

// ── 视图切换（持久化到 localStorage） ──
const viewMode = useViewPreference('mappings_view_mode', 'row')

const loading = ref(true)
const error = ref(null)
const mappings = ref([])
const currentMapping = ref(null)

// ── Form drawer ──
const showFormDrawer = ref(false)
const submitting = ref(false)
const formAliasInput = ref(null)
const isEditing = ref(false)
const form = ref({ alias: '' })

// ── Delete modal ──
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingItem = ref(null)

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

// 当前表单中的虚拟模型ID（编辑时来自 currentMapping，添加时来自 form）
const formAlias = computed(() =>
  isEditing.value && currentMapping.value
    ? currentMapping.value.alias_name
    : form.value.alias
)

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
    await apiRemoveMappingModel(modelId)
    bindingList.value = bindingList.value.filter(b => b.id !== modelId)
    // 同步更新 mappings 列表中的 bound_models
    const m = mappings.value.find(m => m.alias_name === alias)
    if (m) m.bound_models = m.bound_models.filter(b => b.id !== modelId)
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  }
}

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

const closeForm = () => {
  showFormDrawer.value = false
  currentMapping.value = null
}

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
    if (showDeleteModal.value) {
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
  loadSuppliers()
  document.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.status-badge-active {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 11px;
  font-weight: 500;
}
.status-badge-active { background: #a6e3a118; color: #a6e3a1; }
.status-badge-active::before {
  content: "";
  width: 5px;
  height: 5px;
  border-radius: 50%;
  display: inline-block;
  background: #a6e3a1;
}

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
