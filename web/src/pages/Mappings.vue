<template>
  <div>
    <PageHeader title="虚拟模型" subtitle="管理虚拟模型ID及其绑定的供应商模型">
      <template #action>
        <button @click="openAdd" class="btn btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          添加虚拟模型
        </button>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">Error: {{ error }}</div>
      <div v-else>
        <!-- ═══════════════════════════════════════════
             虚拟模型列表（表格形式）
             ═══════════════════════════════════════════ -->
        <div v-if="mappings.length > 0" class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-gray-500 border-b border-ls-border text-xs">
                <th class="text-left px-5 py-3 font-medium">虚拟模型ID</th>
                <th class="text-left px-5 py-3 font-medium">描述</th>
                <th class="text-left px-5 py-3 font-medium">绑定模型</th>
                <th class="text-left px-5 py-3 font-medium">状态</th>
                <th class="text-left px-5 py-3 font-medium">创建时间</th>
                <th class="text-left px-5 py-3 font-medium">日志</th>
                <th class="text-right px-5 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="m in mappings" :key="m.alias_name"
                class="border-b border-ls-border/50 hover:bg-ls-elevated/30 transition-colors"
                :class="{ 'opacity-50': m.status !== 'active' }">
                <!-- 虚拟模型ID -->
                <td class="px-5 py-3 font-mono text-ls-accent font-semibold">{{ m.alias_name }}</td>
                <!-- 描述 -->
                <td class="px-5 py-3 text-gray-400 text-xs max-w-[200px] truncate" :title="m.description">
                  <span v-if="m.description">{{ m.description }}</span>
                  <span v-else class="text-gray-600">—</span>
                </td>
                <!-- 绑定模型个数 -->
                <td class="px-5 py-3">
                  <span v-if="m.bound_models?.length" class="tag tag-accent">
                    {{ m.bound_models.length }} 个模型
                  </span>
                  <span v-else class="text-gray-600 text-xs">未绑定</span>
                </td>
                <!-- 状态 Toggle -->
                <td class="px-5 py-3">
                  <CCheckbox :model-value="m.status === 'active'" @update:modelValue="(val) => toggleStatus(m, val)" />
                </td>
                <!-- 创建时间 -->
                <td class="px-5 py-3 text-xs text-gray-500">
                  {{ formatDate(m.created_at) }}
                </td>
                <!-- 日志 (icon+使用统计，整体可点击) -->
                <td class="px-5 py-3">
                  <button type="button" @click="openLog(m)" class="model-info-btn" title="使用统计">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                      <rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 17V5"/><path d="M15 17v-8"/>
                    </svg>
                    <span class="text-xs">使用统计</span>
                  </button>
                </td>
                <!-- 操作 -->
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
            </tbody>
          </table>
        </div>

        <!-- ── 空态 ── -->
        <div v-if="mappings.length === 0" class="bg-ls-bg rounded-lg border-2 border-dashed border-ls-border p-12 flex flex-col items-center justify-center gap-3">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="text-gray-600">
            <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
          </svg>
          <p class="text-sm text-gray-500">暂无虚拟模型</p>
          <button @click="openAdd" class="text-xs text-ls-accent hover:text-ls-accentHover">添加第一个虚拟模型 →</button>
        </div>
        <div v-else class="mt-4 flex items-center justify-center gap-2 text-sm text-gray-500">
          共 {{ mappings.length }} 个虚拟模型
        </div>
      </div>
    </div>

    <!-- ═══════════════════════════════════════════
         添加/编辑 虚拟模型 抽屉
         ═══════════════════════════════════════════ -->
    <Drawer v-model="showFormDrawer" :title="isEditing ? '编辑虚拟模型' : '添加虚拟模型'">
      <div class="space-y-5">
        <!-- 虚拟模型ID -->
        <div>
          <label class="form-label">虚拟模型ID <span class="text-red-400">*</span></label>
          <input v-model="form.alias" type="text" placeholder="my-virtual-model"
            class="form-input font-mono" :disabled="isEditing"
            @keyup.enter="submitForm" ref="formAliasInput">
          <p v-if="isEditing" class="text-[10px] text-gray-600 mt-1">虚拟模型ID不可修改</p>
        </div>

        <!-- 描述 -->
        <div>
          <label class="form-label">描述 <span class="text-gray-600 normal-case text-[10px]">(可选)</span></label>
          <textarea v-model="form.description" rows="2" placeholder="描述该虚拟模型的用途..."
            class="form-input resize-none"></textarea>
        </div>

        <!-- ── 绑定模型 ── -->
        <div class="border-t border-ls-border pt-5">
          <label class="form-label">绑定模型</label>
          <div class="bg-ls-bg rounded-lg border border-ls-border p-4 space-y-3">
            <!-- 供应商 + 模型多选 + 添加 -->
            <div class="flex items-end gap-2">
              <div class="flex-1">
                <label class="text-xs text-gray-500 mb-1 block">供应商</label>
                <CSelect v-model="selectedSupplier" :options="supplierOptions" placeholder="选择供应商" />
              </div>
              <div class="flex-1">
                <label class="text-xs text-gray-500 mb-1 block">模型（可多选）</label>
                <div class="relative" ref="modelDropdownRef">
                  <button type="button" @click="showModelDropdown = !showModelDropdown"
                    class="form-input text-left flex items-center justify-between"
                    :class="{ 'border-ls-accent': showModelDropdown }">
                    <span class="truncate" :class="selectedModels.length ? 'text-white' : 'text-gray-500'">
                      <span v-if="selectedModels.length">{{ selectedModels.length }} 个已选</span>
                      <span v-else>选择模型</span>
                    </span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
                      class="text-gray-500 transition-transform flex-shrink-0 ml-2" :class="showModelDropdown ? 'rotate-180' : ''">
                      <polyline points="6 9 12 15 18 9"/>
                    </svg>
                  </button>
                  <!-- 多选下拉列表 -->
                  <div v-if="showModelDropdown"
                    class="absolute z-30 top-full left-0 right-0 mt-1 bg-[#181818] border border-gray-800 rounded-lg shadow-lg shadow-black/30 max-h-48 overflow-y-auto">
                    <div v-if="modelOptions.length === 0" class="px-3 py-2 text-xs text-gray-500">该供应商暂无模型</div>
                    <button v-for="opt in modelOptions" :key="opt.value" type="button"
                      @click="toggleModelSelection(opt.value)"
                      class="w-full text-left px-3 py-2 text-sm transition-colors flex items-center gap-2"
                      :class="selectedModels.includes(opt.value) ? 'bg-ls-accent/10 text-ls-accent' : 'text-white hover:bg-[#242424]'">
                      <span class="w-4 h-4 rounded border flex items-center justify-center flex-shrink-0"
                        :class="selectedModels.includes(opt.value) ? 'bg-ls-accent border-ls-accent' : 'border-gray-600'">
                        <svg v-if="selectedModels.includes(opt.value)" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3">
                          <polyline points="20 6 9 17 4 12"/>
                        </svg>
                      </span>
                      <span class="truncate">{{ opt.label }}</span>
                      <span v-if="opt.model_type" class="text-gray-500 text-[10px] ml-auto flex-shrink-0">{{ opt.model_type }}</span>
                    </button>
                  </div>
                </div>
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
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                        <circle cx="9" cy="6" r="1.5"/><circle cx="15" cy="6" r="1.5"/>
                        <circle cx="9" cy="12" r="1.5"/><circle cx="15" cy="12" r="1.5"/>
                        <circle cx="9" cy="18" r="1.5"/><circle cx="15" cy="18" r="1.5"/>
                      </svg>
                    </td>
                    <td class="py-2">
                      <span class="text-gray-300">{{ b.supplier_name || `供应商${b.supplier_id}` }}</span>
                      <span class="text-gray-600 mx-1">/</span>
                      <span class="font-mono text-ls-accent">{{ b.model_name }}</span>
                    </td>
                    <td class="py-2">
                      <span class="tag" :class="getModelTypeTagClass(b.model_type)">
                        {{ formatModelType(b.model_type) }}
                      </span>
                    </td>
                    <td class="py-2 text-gray-400">
                      {{ formatContextLength(b.context_length) || '—' }}
                    </td>
                    <td class="py-2 text-right">
                      <button @click="openBindingDeleteConfirm(b)" class="text-gray-600 hover:text-red-400 transition-colors p-0.5" title="删除">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                          <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                        </svg>
                      </button>
                    </td>
                  </tr>
                </tbody>
              </table>
              <p class="text-[10px] text-gray-600 mt-2">拖拽行可调整负载均衡中的使用顺序</p>
            </div>
            <p v-else class="text-xs text-gray-500 text-center py-3">
              暂无绑定模型，请求时将直接使用虚拟模型ID
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

    <!-- ── 删除虚拟模型确认 弹窗 ── -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定删除虚拟模型 <strong class='text-white'>${deletingItem?.alias_name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
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
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import LogPanel from './LogPanel.vue'
import CSelect from '@/components/CSelect.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import {
  getSuppliers,
  getMappings,
  bulkUpdateMappings as apiBulkUpdate,
  deleteMapping as apiDelete,
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

// ── Delete modal（虚拟模型） ──
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
const showModelDropdown = ref(false)
const modelDropdownRef = ref(null)
const bindingList = ref([])

const supplierOptions = computed(() =>
  suppliers.value.map(s => ({ label: s.name, value: s.id }))
)
const modelOptions = computed(() => {
  if (!selectedSupplier.value) return []
  const sup = suppliers.value.find(s => s.id === selectedSupplier.value)
  return (sup?.models || []).map(m => ({
    label: m.model_name,
    value: m.model_name,
    model_type: m.model_type,
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
  form.value = { alias: item.alias_name, description: item.description || '' }
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
    toast('请填写虚拟模型ID', 'error')
    return
  }
  submitting.value = true
  try {
    const allMappings = {}
    for (const m of mappings.value) {
      allMappings[m.alias_name] = m.actual_model_id || m.alias_name
    }
    allMappings[form.value.alias] = form.value.alias // 虚拟模型ID 自身作为 actual_model_id
    await apiBulkUpdate(allMappings)
    await loadData()
    closeForm()
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    submitting.value = false
  }
}

// ── 绑定模型操作 ──
const toggleModelSelection = (modelName) => {
  const idx = selectedModels.value.indexOf(modelName)
  if (idx >= 0) {
    selectedModels.value.splice(idx, 1)
  } else {
    selectedModels.value.push(modelName)
  }
}

const addSelectedModels = async () => {
  if (!selectedSupplier.value || selectedModels.value.length === 0) {
    toast('请选择供应商和模型', 'error')
    return
  }
  try {
    const alias = isEditing.value ? form.value.alias : form.value.alias
    for (const modelName of selectedModels.value) {
      // 去重
      if (bindingList.value.some(b => b.supplier_id === selectedSupplier.value && b.model_name === modelName)) {
        continue
      }
      const res = await addMappingModel(alias, {
        supplier_id: selectedSupplier.value,
        model_name: modelName,
      })
      bindingList.value.push({
        id: res.data.id,
        supplier_id: selectedSupplier.value,
        model_name: modelName,
        supplier_name: suppliers.value.find(s => s.id === selectedSupplier.value)?.name || '',
        model_type: res.data.model_type || '',
        context_length: res.data.context_length || null,
      })
    }
    // 添加后清空选择
    selectedSupplier.value = null
    selectedModels.value = []
    showModelDropdown.value = false
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
    await apiRemoveMappingModel(b.id)
    bindingList.value = bindingList.value.filter(item => item.id !== b.id)
    // 同步更新 mappings 列表中的 bound_models
    const m = mappings.value.find(m => m.alias_name === form.value.alias)
    if (m) m.bound_models = m.bound_models.filter(item => item.id !== b.id)
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

// ── 删除虚拟模型 ──
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

// ── 格式化辅助函数 ──
const formatDate = (ts) => {
  if (!ts) return '—'
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return ts
  }
}

const formatModelType = (type) => {
  const map = {
    text: '文本',
    image: '图片',
    code: '代码',
    voice: '语音',
    multimodal: '多模态',
  }
  return map[type] || type || '—'
}

const getModelTypeTagClass = (type) => {
  const map = {
    text: 'tag-accent',
    image: 'tag-warning',
    code: 'tag-success',
    voice: 'tag-danger',
    multimodal: 'tag',
  }
  return map[type] || 'tag'
}

const formatContextLength = (len) => {
  if (!len) return null
  if (len >= 1000) return (len / 1000).toFixed(len % 1000 === 0 ? 0 : 1) + 'K'
  return String(len)
}

// ── 点击外部关闭模型下拉 ──
const handleClickOutside = (e) => {
  if (modelDropdownRef.value && !modelDropdownRef.value.contains(e.target)) {
    showModelDropdown.value = false
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
  document.addEventListener('click', handleClickOutside)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleKeyDown)
  document.removeEventListener('click', handleClickOutside)
})
</script>
