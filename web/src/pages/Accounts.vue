<template>
  <div>
    <PageHeader title="供应商管理" subtitle="添加、编辑和删除 ModelScope 供应商">
      <template #action>
        <div class="flex items-center gap-3">
          <!-- ── 视图切换器 ── -->
          <ViewToggle v-model="viewMode" />

          <button @click="openAdd" class="btn btn-primary">
            <CIcon name="plus" :stroke-width="2.5" />
            添加供应商
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="px-6 md:px-8 py-6">
      <PageState :loading="loading" :error="error">

      <!-- ═══════════════════════════════════════════
           视图 1：卡片行（默认）
           ═══════════════════════════════════════════ -->
      <div v-if="viewMode === 'row'" class="space-y-3">
        <div v-for="acc in suppliers" :key="acc.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 flex items-center justify-between hover:border-ls-dim/50 transition-all neon-glow"
          :class="{ 'opacity-50': acc.status !== 'active' }">
          <div class="flex items-center gap-4 flex-1 min-w-0">
            <Avatar :text="acc.name" />
            <div class="min-w-0">
              <p class="font-medium text-sm text-ls-text truncate">{{ acc.name }}</p>
              <p class="text-xs text-ls-muted mt-0.5">{{ maskKey(acc.api_key) }}</p>
              <div class="flex items-center gap-1 flex-wrap mt-2">
                <template v-if="(acc.models || []).length > 0">
                  <span v-for="(m, i) in acc.models.slice(0, 3)" :key="i"
                    class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border gap-1">
                    <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: modelTypeColor(m.model_type) }"></span>
                    <span class="text-ls-text">{{ m.model_name }}</span>
                    <span v-if="m.context_length" class="text-ls-muted">({{ formatContextLength(m.context_length) }})</span>
                  </span>
                  <span v-if="acc.models.length > 3"
                    class="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border text-ls-muted">
                    +{{ acc.models.length - 3 }}
                  </span>
                </template>
                <!-- 模型用量入口 -->
                <button @click="openModelInfo(acc)" class="model-info-btn" title="查看模型用量与限制">
                  <CIcon name="chart" :size="12" :stroke-width="2.2" />
                </button>
              </div>
            </div>
          </div>
          <div class="flex items-center gap-6 flex-shrink-0">
            <div class="text-xs text-ls-muted w-28">
              <span class="text-ls-text font-medium">{{ acc.quota_remaining }}</span> / {{ acc.quota_limit }}
              <ProgressBar :pct="usagePct(acc)" class="mt-1" />
            </div>
            <div class="flex items-center gap-1">
              <CCheckbox :model-value="acc.status === 'active'" @update:modelValue="(val) => toggleSupplier(val, acc)" />
            </div>
            <IconButton icon="edit" title="编辑" @click="openEdit(acc)" />
            <IconButton icon="trash" title="删除" tone="danger" @click="openDeleteConfirm(acc)" />
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 2：网格卡片
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="acc in suppliers" :key="acc.id"
          class="bg-ls-card rounded-lg border border-ls-border p-5 hover:border-ls-dim/50 transition-all flex flex-col gap-3 neon-glow"
          :class="{ 'opacity-50': acc.status !== 'active' }">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-3 min-w-0">
              <Avatar :text="acc.name" />
              <div class="min-w-0">
                <p class="font-medium text-sm text-ls-text truncate">{{ acc.name }}</p>
                <p class="text-[11px] text-ls-muted mt-0.5 truncate font-mono">{{ maskKey(acc.api_key) }}</p>
              </div>
            </div>
            <StatusBadge :active="acc.status === 'active'" />
          </div>

          <!-- 配额（短进度条） -->
          <div class="text-xs text-ls-muted">
            <div class="flex justify-between mb-1">
              <span>配额</span>
              <span><span class="text-ls-text font-medium">{{ acc.quota_remaining }}</span> / {{ acc.quota_limit }}</span>
            </div>
            <ProgressBar :pct="usagePct(acc)" width="w-24" />
          </div>

          <!-- 支持模型预览 -->
          <div class="text-xs">
            <span class="text-ls-muted">模型</span>
            <div v-if="(acc.models || []).length > 0" class="flex items-center gap-1 flex-wrap mt-1">
              <span v-for="(m, i) in acc.models.slice(0, 3)" :key="i"
                class="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] bg-ls-elevated border border-ls-border">
                <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: modelTypeColor(m.model_type) }"></span>
                <span class="text-ls-dim">{{ m.model_name }}</span>
              </span>
              <span v-if="(acc.models || []).length > 3" class="text-[10px] text-ls-muted">+{{ acc.models.length - 3 }}</span>
            </div>
            <span v-else class="text-ls-muted">暂未配置</span>
          </div>

          <!-- 操作行 -->
          <div class="flex items-center justify-between pt-3 border-t border-ls-border">
            <CCheckbox :model-value="acc.status === 'active'" @update:modelValue="(val) => toggleSupplier(val, acc)" />
            <div class="flex items-center gap-2">
              <button @click="openModelInfo(acc)" class="model-info-link" title="查看模型用量与限制">
                用量
              </button>
              <span class="text-ls-border">·</span>
              <IconButton icon="edit" title="编辑" @click="openEdit(acc)" />
              <IconButton icon="trash" title="删除" tone="danger" @click="openDeleteConfirm(acc)" />
            </div>
          </div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 3：表格
           ═══════════════════════════════════════════ -->
      <CTable v-else-if="viewMode === 'table'">
        <thead>
          <tr>
            <th class="text-left">供应商</th>
            <th class="text-left">状态</th>
            <th class="text-left">配额</th>
            <th class="text-left">模型数</th>
            <th class="text-left">模型用量</th>
            <th class="text-right">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="acc in suppliers" :key="acc.id"
            :class="{ 'opacity-50': acc.status !== 'active' }">
            <td>
              <div class="flex items-center gap-3">
                <Avatar :text="acc.name" size="sm" />
                <div>
                  <p class="font-medium text-ls-text">{{ acc.name }}</p>
                  <p class="text-xs text-ls-muted font-mono">{{ maskKey(acc.api_key) }}</p>
                </div>
              </div>
            </td>
            <td>
              <CCheckbox :model-value="acc.status === 'active'" @update:modelValue="(val) => toggleSupplier(val, acc)" />
            </td>
            <td class="text-xs">
              <span class="text-ls-text">{{ acc.quota_remaining }}</span>
              <span class="text-ls-muted"> / {{ acc.quota_limit }}</span>
              <ProgressBar :pct="usagePct(acc)" class="mt-1" />
            </td>
            <td class="text-xs text-ls-dim">{{ (acc.models || []).length }}</td>
            <td>
              <button @click="openModelInfo(acc)" class="model-info-btn" title="查看模型用量与限制">
                <CIcon name="chart" :size="12" :stroke-width="2.2" />
                <span class="text-xs">查看用量</span>
              </button>
            </td>
            <td>
              <div class="flex items-center justify-end gap-1">
                <IconButton icon="edit" title="编辑" @click="openEdit(acc)" />
                <IconButton icon="trash" title="删除" tone="danger" @click="openDeleteConfirm(acc)" />
              </div>
            </td>
          </tr>
          <tr v-if="suppliers.length === 0">
            <td colspan="6" class="py-8 text-center text-ls-muted">尚未配置供应商，前往供应商管理页面添加。</td>
          </tr>
        </tbody>
      </CTable>

      <!-- ── 底部统计 ── -->
      <div class="mt-6 flex items-center justify-center gap-2 text-sm text-ls-muted">
        共 {{ suppliers.length }} 个供应商 · {{ activeCount }} 个活跃
      </div>
      </PageState>
    </div>

    <!-- ── 添加供应商 抽屉 ── -->
    <Drawer v-model="showAddDrawer" title="添加供应商">
      <div class="space-y-4">
        <FormField label="别名">
          <input v-model="newSupplier.name" type="text" placeholder="如：智谱、阿里云"
            class="form-input" @keyup.enter="addSupplier" ref="addNameInput">
        </FormField>
        <FormField label="API Key">
          <input v-model="newSupplier.api_key" type="password" placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
            class="form-input font-mono" @keyup.enter="addSupplier" autocomplete="new-password">
        </FormField>
        <FormField label="Base URL">
          <input v-model="newSupplier.base_url" type="text" placeholder="https://api-inference.modelscope.cn/v1"
            class="form-input font-mono" @keyup.enter="addSupplier">
        </FormField>

        <!-- ── 支持模型 ── -->
        <ModelListEditor :models="newSupplier.models" animate
          @add="addNewModel" @remove="removeNewModel" />
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
        <FormField label="别名">
          <input v-model="editingSupplier.name" type="text" placeholder="如：智谱、阿里云"
            class="form-input" @keyup.enter="saveEdit">
        </FormField>
        <FormField label="API Key">
          <div class="relative">
            <input :type="showApiKey ? 'text' : 'password'" v-model="editingSupplier.api_key"
              placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              class="form-input pr-10 font-mono" @keyup.enter="saveEdit" autocomplete="new-password">
            <button type="button" @click="showApiKey = !showApiKey"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-ls-muted hover:text-ls-text p-1" title="显示/隐藏">
              <CIcon v-if="showApiKey" name="eye" />
              <CIcon v-else name="eye-off" />
            </button>
          </div>
        </FormField>
        <FormField label="Base URL">
          <input v-model="editingSupplier.base_url" type="text" placeholder="https://api-inference.modelscope.cn/v1"
            class="form-input font-mono" @keyup.enter="saveEdit">
        </FormField>
        <FormField label="状态">
          <div class="flex items-center gap-3">
            <CCheckbox :model-value="editingSupplier.status === 'active'" @update:modelValue="(val) => editingSupplier.status = val ? 'active' : 'disabled'" />
            <span class="text-sm" :class="editingSupplier.status === 'active' ? 'text-green-400' : 'text-ls-muted'">
              {{ editingSupplier.status === 'active' ? '启用' : '禁用' }}
            </span>
          </div>
        </FormField>

        <!-- ── 支持模型 ── -->
        <ModelListEditor :models="editingSupplier.models" empty-text="暂无配置模型"
          @add="addEditModel" @remove="removeEditModel" />
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
      :message="`确定要删除供应商 <strong class='text-ls-text'>${deletingSupplier?.name || ''}</strong> 吗？<br><span class='text-ls-muted text-xs'>此操作不可撤销</span>`"
      danger
      :confirm-text="deleting ? '删除中...' : '确认删除'"
      :disabled="deleting"
      @confirm="confirmDelete"
    />

    <!-- ── 删除模型确认 弹窗 ── -->
    <ConfirmModal
      v-model="showModelDeleteModal"
      title="确认删除模型"
      :message="`确定要删除模型 <strong class='text-ls-text font-mono'>${pendingModelDelete?.name || ''}</strong> 吗？<br><span class='text-ls-muted text-xs'>此操作不可撤销</span>`"
      danger
      @confirm="confirmModelDelete"
    />

    <!-- ── 模型用量详情 抽屉 ── -->
    <Drawer v-model="showModelInfoDrawer" :title="`${modelInfoSupplier?.name || ''} · 模型用量`" width="720px">
      <div class="text-xs text-ls-muted mb-4">
        共 {{ modelInfoRows.length }} 个模型 · 展示各模型的配额限制与今日用量
      </div>
      <CTable v-if="modelInfoRows.length > 0" pad="sm">
        <thead>
          <tr>
            <th class="text-left">模型</th>
            <th class="text-left">类型</th>
            <th class="text-left">配额 (剩余/上限)</th>
            <th class="text-right">Token (今日)</th>
            <th class="text-center">状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="m in modelInfoRows" :key="m.model_name">
            <td class="font-mono text-xs text-ls-text">{{ m.model_name }}</td>
            <td>
              <span class="inline-flex items-center gap-1.5">
                <span class="w-1.5 h-1.5 rounded-full flex-shrink-0" :style="{ background: modelTypeColor(m.model_type) }"></span>
                <span class="text-xs text-ls-dim">{{ modelTypeLabel(m.model_type) }}</span>
              </span>
            </td>
            <td class="text-xs">
              <span v-if="m.quota_limit > 0" class="text-ls-dim">
                <span class="text-ls-text font-medium">{{ m.quota_remaining }}</span> / {{ m.quota_limit }}
              </span>
              <span v-else class="text-ls-muted">—</span>
            </td>
            <td class="text-right">
              <TokenStack :input="m.today_input_tokens || 0" :output="m.today_output_tokens || 0" compact />
            </td>
            <td class="text-center">
              <span v-if="m.is_unavailable" class="tag tag-danger">不可用</span>
              <span v-else class="tag tag-success">正常</span>
            </td>
          </tr>
        </tbody>
      </CTable>
      <div v-else class="text-center py-16 text-ls-muted text-sm">
        <CIcon name="chart" :size="40" :stroke-width="1.5" class="mx-auto mb-3 text-ls-muted" />
        暂无模型用量数据
      </div>
    </Drawer>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, inject } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import Drawer from '@/components/Drawer.vue'
import ConfirmModal from '@/components/ConfirmModal.vue'
import CTable from '@/components/CTable.vue'
import Avatar from '@/components/Avatar.vue'
import StatusBadge from '@/components/StatusBadge.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import IconButton from '@/components/IconButton.vue'
import CIcon from '@/components/CIcon.vue'
import FormField from '@/components/FormField.vue'
import ModelListEditor from '@/components/ModelListEditor.vue'
import TokenStack from '@/components/TokenStack.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import ViewToggle from '@/components/ViewToggle.vue'
import { useViewPreference } from '@/composables/useViewPreference'
import { maskKey, formatContextLength } from '@/utils/format'
import { modelTypeColor, modelTypeLabel } from '@/constants/modelType'
import { getSuppliers, createSupplier as apiCreateSupplier, updateSupplier as apiUpdateSupplier, deleteSupplier as apiDeleteSupplier, toggleSupplier as apiToggleSupplier, getSupplierModels, bulkSetSupplierModels as apiBulkSetSupplierModels, getModelQuotas } from '@/api'

const toast = inject('$toast')

// ── 视图切换（持久化到 localStorage） ──
const viewMode = useViewPreference('suppliers_view_mode', 'row')

// ── State ──
const loading = ref(true)
const error = ref(null)
const suppliers = ref([])
const activeCount = computed(() => suppliers.value.filter(a => a.status === 'active').length)

// ── 模型用量数据（/api/model-quota） ──
const modelQuotaMap = ref({}) // { [supplier_id]: [quotaItems] }
const showModelInfoDrawer = ref(false)
const modelInfoSupplier = ref(null)

// 合并该供应商的配置模型与用量数据（左连接：以配置模型为准，无用量记录显示 —）
const modelInfoRows = computed(() => {
  const acc = modelInfoSupplier.value
  if (!acc) return []
  const quotas = modelQuotaMap.value[acc.id] || []
  const quotaByName = {}
  for (const q of quotas) quotaByName[q.model_name] = q
  return (acc.models || []).map(m => {
    const q = quotaByName[m.model_name] || {}
    return {
      model_name: m.model_name,
      model_type: m.model_type,
      quota_remaining: q.quota_remaining || 0,
      quota_limit: q.quota_limit || 0,
      today_input_tokens: q.today_input_tokens || 0,
      today_output_tokens: q.today_output_tokens || 0,
      is_unavailable: q.is_unavailable || false,
    }
  })
})

const openModelInfo = (acc) => {
  modelInfoSupplier.value = acc
  showModelInfoDrawer.value = true
}

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

const openModelDeleteConfirm = (source, idx) => {
  const model = source === 'new'
    ? newSupplier.value.models[idx]
    : editingSupplier.value.models[idx]
  pendingModelDelete.value = { name: model?.model_name || '(未命名)', source, idx }
  showModelDeleteModal.value = true
}

// ── Helpers ──
const usagePct = (acc) => {
  if (!acc.quota_limit || acc.quota_limit === 0) return 0
  return Math.round((acc.quota_limit - (acc.quota_remaining || 0)) / acc.quota_limit * 100)
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
    // Load model-level quotas and group by supplier_id
    try {
      const mqRes = await getModelQuotas()
      const map = {}
      for (const mq of (mqRes.data || [])) {
        if (!map[mq.supplier_id]) map[mq.supplier_id] = []
        map[mq.supplier_id].push(mq)
      }
      modelQuotaMap.value = map
    } catch (e) {
      console.error('Failed to load model quotas:', e)
    }
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

// ── Toggle (checkbox) ──
const toggleSupplier = async (enabled, acc) => {
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

onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* ── 模型用量入口（网格卡片：文字链接） ── */
.model-info-link {
  font-size: 12px;
  color: var(--accent);
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  transition: color .15s;
}
.model-info-link:hover {
  color: #00ffff;
}
</style>
