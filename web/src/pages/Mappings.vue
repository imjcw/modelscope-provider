<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="智能路由 // Smart Routing" subtitle="// 管理智能路由ID及其绑定的供应商模型">
      <template #action>
        <button @click="openAdd" class="btn btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          添加智能路由
        </button>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6">
      <PageState :loading="loading" :error="error">
        <!-- ═══════════════════════════════════════════
             智能路由列表（表格形式）
             ═══════════════════════════════════════════ -->
        <CTable v-if="mappings.length > 0">
          <thead>
            <tr>
              <th class="text-left">智能路由ID</th>
              <th class="text-left">绑定模型</th>
              <th class="text-left">状态</th>
              <th class="text-left">创建时间</th>
              <th class="text-left">日志</th>
              <th class="text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in mappings" :key="m.alias_name"
              :class="{ 'opacity-50': m.status !== 'active' }">
              <!-- 智能路由ID -->
              <td class="font-mono text-ls-accent font-semibold">{{ m.alias_name }}</td>
              <!-- 绑定模型个数 -->
              <td>
                <span v-if="m.bound_models?.length" class="tag tag-accent">
                  {{ m.bound_models.length }} 个模型
                </span>
                <span v-else class="text-ls-muted text-xs">未绑定</span>
              </td>
              <!-- 状态 Toggle -->
              <td>
                <CCheckbox :model-value="m.status === 'active'" @update:modelValue="(val) => toggleStatus(m, val)" />
              </td>
              <!-- 创建时间 -->
              <td class="text-xs text-ls-muted">
                {{ formatDate(m.created_at) }}
              </td>
              <!-- 日志 (icon+使用统计，整体可点击) -->
              <td>
                <button type="button" @click="openLog(m)" class="model-info-btn" title="使用统计">
                  <CIcon name="chart" :size="12" :stroke-width="2.2" />
                </button>
              </td>
              <!-- 操作 -->
              <td>
                <div class="flex items-center justify-end gap-1">
                  <IconButton icon="edit" title="编辑" aria-label="编辑" padded @click="openEdit(m)" />
                  <IconButton icon="trash" title="删除" aria-label="删除" tone="danger" padded @click="openDeleteConfirm(m)" />
                </div>
              </td>
            </tr>
          </tbody>
        </CTable>

        <!-- ── 空态 ── -->
        <EmptyState v-if="mappings.length === 0" text="暂无智能路由">
          <template #icon>
            <CIcon name="link" :size="32" :stroke-width="1.5" class="text-ls-muted" />
          </template>
          <template #action>
            <button @click="openAdd" class="text-xs text-ls-accent hover:text-ls-accentHover">添加第一个智能路由 →</button>
          </template>
        </EmptyState>
        <div v-else class="mt-4 flex items-center justify-center gap-2 text-sm text-ls-muted">
          共 {{ mappings.length }} 个智能路由
        </div>
      </PageState>
    </div>

    <!-- ═══════════════════════════════════════════
         添加/编辑 智能路由 抽屉
         ═══════════════════════════════════════════ -->
    <Drawer v-model="showFormDrawer" :title="isEditing ? '编辑智能路由' : '添加智能路由'">
      <div class="space-y-5">
        <!-- 智能路由ID -->
        <FormField label="智能路由ID" required>
          <input v-model="form.alias" type="text" placeholder="my-smart-route"
            class="form-input font-mono"
            @keyup.enter="submitForm" ref="formAliasInput">
        </FormField>

        <!-- 描述 -->
        <FormField label="描述" optional>
          <textarea v-model="form.description" rows="2" placeholder="描述该智能路由的用途..."
            class="form-input resize-none"></textarea>
        </FormField>

        <!-- ── 绑定模型 ── -->
        <div class="border-t border-ls-border pt-5">
          <label class="form-label">绑定模型</label>
          <div class="bg-ls-bg rounded-lg border border-ls-border p-4 space-y-3">
            <!-- 供应商 + 模型多选 + 添加 -->
            <div class="flex items-end gap-2">
              <div class="flex-1">
                <label class="text-xs text-ls-muted mb-1 block">供应商</label>
                <CSelect v-model="selectedSupplier" :options="supplierOptions" placeholder="选择供应商" />
              </div>
              <div class="flex-1">
                <label class="text-xs text-ls-muted mb-1 block">模型（可多选）</label>
                <CMultiSelect v-model="selectedModels" :options="modelOptions"
                  placeholder="选择模型" empty-text="该供应商暂无模型" />
              </div>
              <button @click="addSelectedModels" class="btn btn-secondary" style="height: 38px;"
                :disabled="!selectedSupplier || selectedModels.length === 0">
                添加
              </button>
            </div>

            <!-- 已绑定列表（可拖动排序） -->
            <div v-if="bindingList.length > 0" class="mt-2">
              <table class="w-full text-xs">
                <thead>
                  <tr class="text-gray-500 border-b border-ls-border/60">
                    <th class="text-left py-2 font-medium w-8"></th>
                    <th class="text-left py-2 font-medium">模型</th>
                    <th class="text-left py-2 font-medium">模态</th>
                    <th class="text-left py-2 font-medium">上下文</th>
                    <th class="text-right py-2 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(b, idx) in bindingList" :key="b.id"
                    class="border-b border-ls-border/40 hover:bg-ls-elevated/20 transition-colors group"
                    :class="{ 'opacity-50': dragIndex === idx }"
                    draggable="true"
                    @dragstart="onDragStart(idx)"
                    @dragover.prevent="onDragOver(idx)"
                    @dragend="onDragEnd"
                    @drop.prevent="onDrop(idx)">
                    <td class="py-2 cursor-grab text-gray-600 hover:text-gray-400">
                      <CIcon name="grip" :size="12" />
                    </td>
                    <td class="py-2">
                      <span class="text-gray-300">{{ b.supplier_name || `供应商${b.supplier_id}` }}</span>
                      <span class="text-gray-600 mx-1">/</span>
                      <span class="font-mono text-ls-accent">{{ b.model_name }}</span>
                    </td>
                    <td class="py-2">
                      <span class="tag" :class="modelTypeTagClass(b.model_type)">
                        {{ modelTypeLabel(b.model_type) }}
                      </span>
                    </td>
                    <td class="py-2 text-gray-400">
                      {{ formatContextLength(b.context_length) || '—' }}
                    </td>
                    <td class="py-2 text-right">
                      <button @click="openBindingDeleteConfirm(b)" class="text-gray-600 hover:text-red-400 transition-colors p-0.5" title="删除">
                        <CIcon name="x" :size="12" />
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="text-[10px] text-gray-600 mt-2">拖拽行可调整负载均衡中的使用顺序</p>
            </div>
            <p v-else class="text-xs text-gray-500 text-center py-3">
              暂无绑定模型，请求时将直接使用智能路由ID
            </p>
          </div>
        </div>
      </div>

      <template #footer>
        <button @click="closeForm" class="btn btn-secondary btn-esc">取消</button>
        <button @click="submitForm" class="btn btn-primary btn-enter" :disabled="submitting">
          {{ submitting ? '保存中...' : isEditing ? '保存' : '添加' }}
        </button>
      </template>
    </Drawer>

    <!-- ── 删除智能路由确认 弹窗 ── -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定删除智能路由 <strong class='text-white'>${deletingItem?.alias_name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />

    <!-- ── 删除绑定模型确认 弹窗 ── -->
    <ConfirmModal
      v-model="showBindingDeleteModal"
      title="确认删除绑定"
      :message="`确定删除绑定模型 <strong class='text-white'>${deletingBinding?.model_name || ''}</strong> 吗？`"
      danger
      confirm-text="确认删除"
      @confirm="confirmBindingDelete"
    />

    <!-- ── 日志（使用情况 + 操作历史）抽屉 ── -->
    <LogPanel v-model="showLogPanel" :alias="selectedMapping?.alias_name || ''" />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import CTable from '@/components/CTable.vue'
import EmptyState from '@/components/EmptyState.vue'
import FormField from '@/components/FormField.vue'
import CMultiSelect from '@/components/CMultiSelect.vue'
import CIcon from '@/components/CIcon.vue'
import IconButton from '@/components/IconButton.vue'
import LogPanel from './LogPanel.vue'
import CSelect from '@/components/CSelect.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import { formatDate, formatContextLength } from '@/utils/format'
import { modelTypeLabel, modelTypeTagClass } from '@/constants/modelType'
import {
  getSuppliers,
  getMappings,
  bulkUpdateMappings as apiBulkUpdate,
  deleteMapping as apiDelete,
  renameMapping as apiRenameMapping,
  getMappingModels,
  addMappingModel,
  removeMappingModel as apiRemoveMappingModel,
  reorderMappingModels,
  toggleMappingStatus as apiToggleStatus,
} from '@/api'

const toast = inject('$toast')

const loading = ref(true)
const error = ref(null)
const mappings = ref([])

// ── Form drawer ──
const showFormDrawer = ref(false)
const submitting = ref(false)
const formAliasInput = ref(null)
const isEditing = ref(false)
const form = ref({ alias: '', description: '' })

// ── Delete modal（智能路由） ──
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingItem = ref(null)

// ── Delete modal（绑定模型） ──
const showBindingDeleteModal = ref(false)
const deletingBinding = ref(null)

// ── 日志抽屉 ──
const showLogPanel = ref(false)
const selectedMapping = ref(null)

// ── 绑定模型 ──
const suppliers = ref([])
const selectedSupplier = ref(null)
const selectedModels = ref([])
const bindingList = ref([])

const supplierOptions = computed(() =>
  suppliers.value.map(s => ({ label: s.name, value: s.id }))
)
const modelOptions = computed(() => {
  if (!selectedSupplier.value) return []
  const sup = suppliers.value.find(s => s.id === selectedSupplier.value)
  return (sup?.models || []).map(m => ({
    label: m.model_name,
    value: m.id,
    extra: m.model_type,
  }))
})

// ── 拖拽排序状态 ──
const dragIndex = ref(null)
const dragOverIndex = ref(null)

// ── 数据加载 ──
const loadSuppliers = async () => {
  try {
    const res = await getSuppliers()
    suppliers.value = res.data || []
  } catch (e) {
    console.error('Failed to load suppliers:', e)
  }
}

const loadData = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await getMappings()
    mappings.value = res.data || []
    // Load bound models for each mapping
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

// ── 表单操作 ──
const openAdd = async () => {
  isEditing.value = false
  form.value = { alias: '', description: '' }
  bindingList.value = []
  selectedSupplier.value = null
  selectedModels.value = []
  showFormDrawer.value = true
  await nextTick()
  formAliasInput.value?.focus()
}

const openEdit = async (item) => {
  isEditing.value = true
  form.value = { alias: item.alias_name, description: item.description || '', _oldAlias: item.alias_name }
  bindingList.value = []
  selectedSupplier.value = null
  selectedModels.value = []
  // Load bound models
  try {
    const res = await getMappingModels(item.alias_name)
    bindingList.value = (res.data || []).map(b => ({
      ...b,
      supplier_name: suppliers.value.find(s => s.id === b.supplier_id)?.name || '',
    }))
  } catch (e) {
    console.error('Failed to load mapping models:', e)
  }
  showFormDrawer.value = true
}

const closeForm = () => {
  showFormDrawer.value = false
}

const submitForm = async () => {
  if (!form.value.alias) {
    toast('请填写智能路由ID', 'error')
    return
  }
  submitting.value = true
  try {
    // Rename: changed alias in edit mode — use dedicated rename API (cascades to mapping_models)
    if (isEditing.value && form.value.alias !== form.value._oldAlias) {
      await apiRenameMapping(form.value._oldAlias, form.value.alias)
      // Remove old entry from list so loadData picks up the renamed one
      const idx = mappings.value.findIndex(m => m.alias_name === form.value._oldAlias)
      if (idx !== -1) mappings.value.splice(idx, 1)
      // Update the alias reference in bound models list
      const m = mappings.value.find(m => m.alias_name === form.value.alias)
      if (m) m.description = form.value.description
      await loadData()
      closeForm()
      return
    }
    const allMappings = {}
    for (const m of mappings.value) {
      allMappings[m.alias_name] = m.actual_model_id || m.alias_name
    }
    allMappings[form.value.alias] = form.value.alias // 智能路由ID 自身作为 actual_model_id
    await apiBulkUpdate(allMappings)

    // 创建模式：别名创建后，持久化暂存的绑定模型
    if (!isEditing.value && bindingList.value.length > 0) {
      for (const b of bindingList.value) {
        await addMappingModel(form.value.alias, {
          supplier_model_id: b.supplier_model_id,
        })
      }
    }

    await loadData()
    closeForm()
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    submitting.value = false
  }
}

// ── 绑定模型操作 ──
const addSelectedModels = async () => {
  if (!selectedSupplier.value || selectedModels.value.length === 0) {
    toast('请选择供应商和模型', 'error')
    return
  }
  const sup = suppliers.value.find(s => s.id === selectedSupplier.value)
  try {
    const alias = form.value.alias
    for (const supplierModelId of selectedModels.value) {
      // 去重
      if (bindingList.value.some(b => b.supplier_model_id === supplierModelId)) {
        continue
      }
      if (isEditing.value) {
        // 编辑模式：别名已存在，立即调用 API 持久化
        const res = await addMappingModel(alias, {
          supplier_model_id: supplierModelId,
        })
        bindingList.value.push({
          id: res.data.id,
          supplier_model_id: supplierModelId,
          supplier_id: res.data.supplier_id,
          model_name: res.data.model_name,
          supplier_name: sup?.name || '',
          model_type: res.data.model_type || '',
          context_length: res.data.context_length || null,
        })
      } else {
        // 创建模式：别名尚未创建（外键约束），先暂存本地，提交时再持久化
        const modelInfo = (sup?.models || []).find(m => m.id === supplierModelId)
        bindingList.value.push({
          id: `pending-${Date.now()}-${supplierModelId}`,
          supplier_model_id: supplierModelId,
          supplier_id: selectedSupplier.value,
          model_name: modelInfo?.model_name || '',
          supplier_name: sup?.name || '',
          model_type: modelInfo?.model_type || '',
          context_length: modelInfo?.context_length || null,
          _pending: true,
        })
      }
    }
    // 添加后清空选择
    selectedSupplier.value = null
    selectedModels.value = []
  } catch (e) {
    toast('添加失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  }
}

const openBindingDeleteConfirm = (b) => {
  deletingBinding.value = b
  showBindingDeleteModal.value = true
}

const confirmBindingDelete = async () => {
  if (!deletingBinding.value) return
  const b = deletingBinding.value
  try {
    // 暂存（未持久化）的绑定仅从本地列表移除
    if (!b._pending) {
      await apiRemoveMappingModel(b.id)
    }
    bindingList.value = bindingList.value.filter(item => item.id !== b.id)
    // 同步更新 mappings 列表中的 bound_models
    const m = mappings.value.find(m => m.alias_name === form.value.alias)
    if (m && m.bound_models) m.bound_models = m.bound_models.filter(item => item.id !== b.id)
    showBindingDeleteModal.value = false
    deletingBinding.value = null
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  }
}

// ── 拖拽排序 ──
const onDragStart = (idx) => {
  dragIndex.value = idx
}
const onDragOver = (idx) => {
  dragOverIndex.value = idx
}
const onDragEnd = () => {
  dragIndex.value = null
  dragOverIndex.value = null
}
const onDrop = async (targetIdx) => {
  const sourceIdx = dragIndex.value
  dragIndex.value = null
  dragOverIndex.value = null
  if (sourceIdx === null || sourceIdx === targetIdx) return
  // 重新排序数组
  const item = bindingList.value.splice(sourceIdx, 1)[0]
  bindingList.value.splice(targetIdx, 0, item)
  // 含暂存（未持久化）绑定时仅本地排序，提交时按列表顺序持久化
  if (bindingList.value.some(b => b._pending)) return
  // 通知后端更新顺序
  try {
    const orderedIds = bindingList.value.map(b => b.id)
    await reorderMappingModels(form.value.alias, orderedIds)
  } catch (e) {
    toast('排序更新失败: ' + (e.message || ''), 'error')
  }
}

// ── 状态切换 ──
const toggleStatus = async (item, val) => {
  const newStatus = val ? 'active' : 'disabled'
  try {
    await apiToggleStatus(item.alias_name)
    item.status = newStatus
  } catch (e) {
    toast('状态更新失败: ' + (e.message || ''), 'error')
  }
}

// ── 使用情况 / 操作日志 ──
const openLog = (item) => {
  selectedMapping.value = item
  showLogPanel.value = true
}

// ── 删除智能路由 ──
const openDeleteConfirm = (item) => {
  deletingItem.value = item
  showDeleteModal.value = true
}

const confirmDelete = async () => {
  if (!deletingItem.value) return
  deleting.value = true
  try {
    await apiDelete(deletingItem.value.alias_name)
    await loadData()
    showDeleteModal.value = false
    deletingItem.value = null
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  } finally {
    deleting.value = false
  }
}

// ── 键盘快捷键 ──
const handleKeyDown = (e) => {
  if (e.key === 'Escape') {
    if (showDeleteModal.value || showBindingDeleteModal.value) return // 让弹窗自身处理
    if (showFormDrawer.value) closeForm()
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
