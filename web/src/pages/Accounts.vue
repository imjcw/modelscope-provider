<template>
  <div>
    <PageHeader title="供应商管理" subtitle="添加、编辑和删除 ModelScope 供应商">
      <template #action>
        <button @click="openAdd" class="btn btn-primary">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          添加供应商
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
        <div v-for="acc in suppliers" :key="acc.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-gray-700 transition-all"
          :class="{ 'opacity-50': acc.status !== 'active' }">
          <div class="flex items-center gap-4 flex-1">
            <div class="w-10 h-10 rounded-md bg-ls-elevated flex items-center justify-center">
              <span class="font-semibold text-sm text-gray-300">{{ (acc.name || '').slice(0, 2).toUpperCase() }}</span>
            </div>
            <div>
              <p class="font-medium text-sm text-white">{{ acc.name }}</p>
              <p class="text-xs text-gray-500 mt-0.5">{{ maskKey(acc.api_key) }}</p>
              <div v-if="acc.models && acc.models.length > 0" class="flex items-center gap-1 flex-wrap mt-2">
                <span v-for="(m, i) in acc.models.slice(0, 3)" :key="i"
                  class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border gap-1">
                  <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: getModelTypeColor(m.model_type) }"></span>
                  <span class="text-white">{{ m.model_name }}</span>
                  <span v-if="m.context_length" class="text-gray-500">({{ formatContextLength(m.context_length) }})</span>
                </span>
                <span v-if="acc.models.length > 3"
                  class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border text-gray-500">
                  +{{ acc.models.length - 3 }}
                </span>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-6">
            <div class="text-xs text-gray-500 w-28">
              <span class="text-white font-medium">{{ acc.quota_remaining }}</span> / {{ acc.quota_limit }}
              <div class="w-20 bg-ls-bg rounded-full h-1 mt-1">
                <div class="bg-ls-accent h-1 rounded-full" :style="{ width: usagePct(acc) + '%' }"></div>
              </div>
            </div>
            <span class="inline-flex items-center rounded-md px-2 py-0.5 text-xs"
              :class="acc.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-ls-elevated text-gray-400'">
              <span class="w-1.5 h-1.5 rounded-full mr-1.5"
                :class="acc.status === 'active' ? 'bg-green-400' : 'bg-gray-500'"></span>
              {{ acc.status === 'active' ? '活跃' : '已禁用' }}
            </span>
            <button @click="openEdit(acc)" class="text-gray-500 hover:text-white transition-colors" title="编辑">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
              </svg>
            </button>
            <button @click="toggleSupplier(acc)" class="text-gray-500 hover:text-white transition-colors" title="切换状态">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M18.36 6.64a9 9 0 1 1-12.73 0"/><line x1="12" y1="2" x2="12" y2="12"/>
              </svg>
            </button>
            <button @click="openDeleteConfirm(acc)" class="text-gray-500 hover:text-red-400 transition-colors" title="删除">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
              </svg>
            </button>
          </div>
        </div>
      </div>

      <div class="mt-6 flex items-center justify-center gap-2 text-sm text-gray-500">
        共 {{ suppliers.length }} 个供应商 · {{ activeCount }} 个活跃
      </div>
      </div>
    </div>

    <!-- ── 添加供应商 抽屉 ── -->
    <Drawer v-model="showAddDrawer" title="添加供应商">
      <div class="space-y-4">
        <div>
          <label class="form-label">别名</label>
          <input v-model="newSupplier.name" type="text" placeholder="如：智谱、阿里云"
            class="form-input" @keyup.enter="addSupplier" ref="addNameInput">
        </div>
        <div>
          <label class="form-label">API Key</label>
          <input v-model="newSupplier.api_key" type="password" placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            class="form-input font-mono" @keyup.enter="addSupplier">
        </div>
        <div>
          <label class="form-label">Base URL</label>
          <input v-model="newSupplier.base_url" type="text" placeholder="https://api-inference.modelscope.cn/v1"
            class="form-input font-mono" @keyup.enter="addSupplier">
        </div>

        <!-- ── 支持模型 ── -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <label class="form-label m-0">支持模型</label>
            <span class="text-[11px] text-gray-500">{{ newSupplier.models.length }} 个模型</span>
          </div>
          <div class="space-y-3">
            <div v-for="(m, idx) in newSupplier.models" :key="idx"
              class="bg-ls-bg rounded-lg border border-ls-border p-3"
              :style="{ animation: 'rowIn .2s ease-out ' + idx * 50 + 'ms both' }">
              <div class="grid grid-cols-1 md:grid-cols-[1fr_140px_120px_28px] gap-3 items-center">
                <input v-model="m.model_name" type="text" placeholder="模型名称，如 qwen-max"
                  class="form-input h-10 px-3 font-mono text-sm" />
                <CSelect v-model="m.model_type" :options="MODEL_TYPE_OPTIONS" size="md" placeholder="类型" />
                <input v-model.number="m.context_length" type="number" placeholder="上下文"
                  class="form-input h-10 px-3 text-sm font-mono" />
                <button type="button" @click="removeNewModel(idx)"
                  class="action-icon" title="删除">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <button type="button" @click="addNewModel"
            class="mt-3 w-full h-10 rounded-lg border border-dashed border-ls-border text-ls-accent hover:text-ls-accentHover hover:border-ls-accent/30 transition-all flex items-center justify-center gap-2 text-sm">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            添加模型
          </button>
        </div>
      </div>
      <template #footer>
        <button @click="closeAdd" class="btn btn-secondary btn-esc">取消</button>
        <button @click="addSupplier" class="btn btn-primary" :disabled="adding">
          {{ adding ? '添加中...' : '添加' }}
        </button>
      </template>
    </Drawer>

    <!-- ── 编辑供应商 抽屉 ── -->
    <Drawer v-model="showEditDrawer" title="编辑供应商">
      <div class="space-y-4">
        <div>
          <label class="form-label">别名</label>
          <input v-model="editingSupplier.name" type="text" placeholder="如：智谱、阿里云"
            class="form-input" @keyup.enter="saveEdit">
        </div>
        <div>
          <label class="form-label">API Key</label>
          <div class="relative">
            <input :type="showApiKey ? 'text' : 'password'" v-model="editingSupplier.api_key"
              placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              class="form-input pr-10 font-mono" @keyup.enter="saveEdit">
            <button type="button" @click="showApiKey = !showApiKey"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white p-1" title="显示/隐藏">
              <svg v-if="showApiKey" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 2.9M5 12h14"/><line x1="1" y1="1" x2="23" y2="23"/>
              </svg>
            </button>
          </div>
        </div>
        <div>
          <label class="form-label">Base URL</label>
          <input v-model="editingSupplier.base_url" type="text" placeholder="https://api-inference.modelscope.cn/v1"
            class="form-input font-mono" @keyup.enter="saveEdit">
        </div>
        <div>
          <label class="form-label">状态</label>
          <CSelect v-model="editingSupplier.status" :options="STATUS_OPTIONS" placeholder="状态" />
        </div>

        <!-- ── 支持模型 ── -->
        <div>
          <div class="flex items-center justify-between mb-3">
            <label class="form-label m-0">支持模型</label>
            <span class="text-[11px] text-gray-500">{{ editingSupplier.models.length }} 个模型</span>
          </div>
          <div v-if="editingSupplier.models.length === 0"
            class="text-center py-6 text-gray-500 text-sm">
            暂无配置模型
          </div>
          <div class="space-y-3">
            <div v-for="(m, idx) in editingSupplier.models" :key="idx"
              class="bg-ls-bg rounded-lg border border-ls-border p-3">
              <div class="grid grid-cols-1 md:grid-cols-[1fr_140px_120px_28px] gap-3 items-center">
                <input v-model="m.model_name" type="text" placeholder="模型名称，如 qwen-max"
                  class="form-input h-10 px-3 font-mono text-sm" />
                <CSelect v-model="m.model_type" :options="MODEL_TYPE_OPTIONS" size="md" placeholder="类型" />
                <input v-model.number="m.context_length" type="number" placeholder="上下文"
                  class="form-input h-10 px-3 text-sm font-mono" />
                <button type="button" @click="removeEditModel(idx)"
                  class="action-icon" title="删除">
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                  </svg>
                </button>
              </div>
            </div>
          </div>
          <button type="button" @click="addEditModel"
            class="mt-3 w-full h-10 rounded-lg border-2 border-dashed border-ls-border text-ls-accent hover:text-ls-accentHover hover:border-ls-accent/30 transition-all flex items-center justify-center gap-2 text-sm">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
            </svg>
            添加模型
          </button>
        </div>
      </div>
      <template #footer>
        <button @click="closeEdit" class="btn btn-secondary btn-esc">取消</button>
        <button @click="saveEdit" class="btn btn-primary" :disabled="saving">
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </template>
    </Drawer>

    <!-- ── 删除确认 弹窗 ── -->
    <ConfirmModal
      v-model="showDeleteModal"
      title="确认删除"
      :message="`确定要删除供应商 <strong class='text-white'>${deletingSupplier?.name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />

    <!-- ── 删除模型确认 弹窗 ── -->
    <ConfirmModal
      v-model="showModelDeleteModal"
      title="确认删除模型"
      :message="`确定要删除模型 <strong class='text-white font-mono'>${pendingModelDelete?.name || ''}</strong> 吗？<br><span class='text-gray-500 text-xs'>此操作不可撤销</span>`"
      danger
      @confirm="confirmModelDelete"
    />
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, nextTick, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import { getSuppliers, createSupplier as apiCreateSupplier, updateSupplier as apiUpdateSupplier, deleteSupplier as apiDeleteSupplier, toggleSupplier as apiToggleSupplier, getSupplierModels, bulkSetSupplierModels as apiBulkSetSupplierModels } from '@/api'
import CSelect from '@/components/CSelect.vue'

const toast = inject('$toast')

// ── Select options ──
const MODEL_TYPE_OPTIONS = [
  { label: '文本', value: 'text' },
  { label: '图像', value: 'image' },
  { label: '代码', value: 'code' },
  { label: '语音', value: 'voice' },
  { label: '多模态', value: 'multimodal' },
]
const STATUS_OPTIONS = [
  { label: '活跃', value: 'active' },
  { label: '已禁用', value: 'disabled' },
]

// ── State ──
const loading = ref(true)
const error = ref(null)
const suppliers = ref([])
const activeCount = computed(() => suppliers.value.filter(a => a.status === 'active').length)

// ── Add drawer ──
const showAddDrawer = ref(false)
const adding = ref(false)
const addNameInput = ref(null)
const newSupplier = ref({ name: '', api_key: '', base_url: '', models: [] })

// ── Edit drawer ──
const showEditDrawer = ref(false)
const saving = ref(false)
const editingSupplier = ref(null)
const showApiKey = ref(false)

// ── Delete confirmation modal ──
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingSupplier = ref(null)

// ── Model delete confirmation modal ──
const showModelDeleteModal = ref(false)
const pendingModelDelete = ref(null) // { name, source: 'new'|'edit', idx }

const confirmModelDelete = () => {
  if (!pendingModelDelete.value) return
  const { source, idx } = pendingModelDelete.value
  if (source === 'new') {
    newSupplier.value.models.splice(idx, 1)
  } else {
    editingSupplier.value.models.splice(idx, 1)
  }
}

const closeModelDeleteConfirm = () => {
  showModelDeleteModal.value = false
  pendingModelDelete.value = null
}

const openModelDeleteConfirm = (source, idx) => {
  const model = source === 'new'
    ? newSupplier.value.models[idx]
    : editingSupplier.value.models[idx]
  pendingModelDelete.value = { name: model?.model_name || '(未命名)', source, idx }
  showModelDeleteModal.value = true
}

// ── Helpers ──
const maskKey = (key) => {
  if (!key || key.length < 20) return '****'
  return key.slice(0, 10) + '****' + key.slice(-10)
}

const usagePct = (acc) => {
  if (!acc.quota_limit || acc.quota_limit === 0) return 0
  return Math.round((acc.quota_limit - (acc.quota_remaining || 0)) / acc.quota_limit * 100)
}

// ── Model helpers ──
const MODEL_TYPE_COLORS = {
  text: '#89b4fa',
  image: '#f0c674',
  code: '#a6e3a1',
  voice: '#cba6f7',
  multimodal: '#f38ba8',
}

const getModelTypeColor = (type) => MODEL_TYPE_COLORS[type] || '#89b4fa'

const formatContextLength = (length) => {
  if (!length) return ''
  if (length >= 1000) return `${Math.round(length / 1000)}K`
  return String(length)
}

const addNewModel = () => {
  newSupplier.value.models.push({ model_name: '', model_type: 'text', context_length: null })
}

const removeNewModel = (idx) => {
  openModelDeleteConfirm('new', idx)
}

const addEditModel = () => {
  editingSupplier.value.models.push({ model_name: '', model_type: 'text', context_length: null })
}

const removeEditModel = (idx) => {
  openModelDeleteConfirm('edit', idx)
}

// ── Data loading ──
const loadData = async () => {
  loading.value = true
  try {
    const res = await getSuppliers()
    suppliers.value = res.data || []
    // Load models concurrently
    const modelResults = await Promise.allSettled(
      suppliers.value.map(s => getSupplierModels(s.id))
    )
    suppliers.value.forEach((s, i) => {
      s.models = modelResults[i].status === 'fulfilled'
        ? (modelResults[i].value.data || [])
        : []
    })
  } catch (e) {
    error.value = e.message || 'Failed to load suppliers'
  }
  loading.value = false
}

// ── Add (drawer) ──
const openAdd = async () => {
  newSupplier.value = { name: '', api_key: '', base_url: '', models: [] }
  showAddDrawer.value = true
  await nextTick()
  addNameInput.value?.focus()
}

const closeAdd = () => {
  showAddDrawer.value = false
}

const addSupplier = async () => {
  if (!newSupplier.value.name || !newSupplier.value.api_key) {
    toast('请填写别名和 API Key', 'error')
    return
  }
  adding.value = true
  try {
    const res = await apiCreateSupplier({
      name: newSupplier.value.name,
      api_key: newSupplier.value.api_key,
      base_url: newSupplier.value.base_url,
    })
    const supplierId = res.data.id
    // Add models if any
    if (newSupplier.value.models.length > 0) {
      await apiBulkSetSupplierModels(supplierId, {
        models: newSupplier.value.models.map(m => ({
          model_name: m.model_name,
          model_type: m.model_type,
          context_length: m.context_length || null,
        })),
      })
    }
    await loadData()
    closeAdd()
  } catch (e) {
    toast('添加失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    adding.value = false
  }
}

// ── Edit (drawer) ──
const openEdit = async (acc) => {
  editingSupplier.value = {
    id: acc.id,
    name: acc.name,
    api_key: acc.api_key,
    base_url: acc.base_url,
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
}

const closeEdit = () => {
  showEditDrawer.value = false
}

const saveEdit = async () => {
  if (!editingSupplier.value) return
  saving.value = true
  try {
    const body = {
      name: editingSupplier.value.name,
      api_key: editingSupplier.value.api_key,
      base_url: editingSupplier.value.base_url,
      status: editingSupplier.value.status,
    }
    const res = await apiUpdateSupplier(editingSupplier.value.id, body)
    const idx = suppliers.value.findIndex(a => a.id === editingSupplier.value.id)
    if (idx !== -1) suppliers.value[idx] = { ...suppliers.value[idx], ...res.data }

    // Update models (bulk replaces all)
    await apiBulkSetSupplierModels(editingSupplier.value.id, {
      models: editingSupplier.value.models.map(m => ({
        model_name: m.model_name,
        model_type: m.model_type,
        context_length: m.context_length || null,
      })),
    })

    await loadData()
    closeEdit()
  } catch (e) {
    toast('保存失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    saving.value = false
  }
}

// ── Toggle ──
const toggleSupplier = async (acc) => {
  try {
    const res = await apiToggleSupplier(acc.id)
    Object.assign(acc, res.data)
  } catch (e) {
    toast('操作失败: ' + (e.message || ''), 'error')
  }
}

// ── Delete (confirmation modal) ──
const openDeleteConfirm = (acc) => {
  deletingSupplier.value = acc
  showDeleteModal.value = true
}

const closeDeleteConfirm = () => {
  showDeleteModal.value = false
  deletingSupplier.value = null
}

const confirmDelete = async () => {
  if (!deletingSupplier.value) return
  deleting.value = true
  try {
    await apiDeleteSupplier(deletingSupplier.value.id)
    suppliers.value = suppliers.value.filter(a => a.id !== deletingSupplier.value.id)
  } catch (e) {
    toast('删除失败: ' + (e.message || ''), 'error')
  } finally {
    deleting.value = false
  }
}

// ── ESC / Enter keyboard shortcuts ──
const handleKeyDown = (e) => {
  if (e.key === 'Escape') {
    if (showModelDeleteModal.value) {
      closeModelDeleteConfirm()
    } else if (showAddDrawer.value) {
      closeAdd()
    } else if (showEditDrawer.value) {
      closeEdit()
    }
  }
  if (e.key === 'Enter' && showModelDeleteModal.value) {
    confirmModelDelete()
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
