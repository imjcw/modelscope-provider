<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="供应商管理 // Suppliers" subtitle="// 添加、编辑和删除 AI 供应商">
      <template #action>
        <div class="flex items-center gap-3">

          <button @click="openAdd" class="btn btn-primary">
            <CIcon name="plus" :stroke-width="2.5" />
            添加供应商
          </button>
        </div>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6">
      <PageState :loading="loading" :error="error">

      <CTable v-if="suppliers.length > 0" class="hover-dim">
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
            </td>
            <td class="text-xs text-ls-dim">{{ (acc.models || []).length }}</td>
            <td>
              <button @click="openModelInfo(acc)" class="model-info-btn" title="查看模型用量与限制">
                <CIcon name="chart" :size="12" :stroke-width="2.2" />
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
          <div class="relative">
            <input type="text" v-model="newSupplier.api_key"
              placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              class="form-input pr-10 font-mono" @keyup.enter="addSupplier"
              autocomplete="off"
              :style="showNewApiKey ? null : { '-webkit-text-security': 'disc', 'text-security': 'disc' }">
            <button type="button" @click="showNewApiKey = !showNewApiKey"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-ls-muted hover:text-ls-text p-1" title="显示/隐藏">
              <CIcon v-if="showNewApiKey" name="eye" />
              <CIcon v-else name="eye-off" />
            </button>
          </div>
        </FormField>
        <FormField label="供应商类型">
          <CSelect v-model="newSupplier.provider_type" :options="providerTypeOptions" placeholder="选择供应商类型" />
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
            <input type="text" v-model="editingSupplier.api_key"
              placeholder="ms-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
              class="form-input pr-10 font-mono" @keyup.enter="saveEdit"
              autocomplete="off"
              :style="showApiKey ? null : { '-webkit-text-security': 'disc', 'text-security': 'disc' }">
            <button type="button" @click="showApiKey = !showApiKey"
              class="absolute right-3 top-1/2 -translate-y-1/2 text-ls-muted hover:text-ls-text p-1" title="显示/隐藏">
              <CIcon v-if="showApiKey" name="eye" />
              <CIcon v-else name="eye-off" />
            </button>
          </div>
        </FormField>
        <FormField label="供应商类型">
          <CSelect v-model="editingSupplier.provider_type" :options="providerTypeOptions" placeholder="选择供应商类型" />
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
    <Drawer v-model="showModelInfoDrawer" :title="`${modelInfoSupplier?.name || ''} · 模型用量`" width="880px">
      <!-- 时间范围 -->
      <div class="flex items-center justify-between mb-4">
        <span class="text-xs text-ls-muted">
          共 {{ modelInfoRows.length }} 个模型
        </span>
        <SegmentedControl v-model="modelInfoDays" :options="MODEL_INFO_DAYS_OPTIONS" size="sm" />
      </div>

      <!-- KPI 卡片 -->
      <div v-if="modelInfoRows.length > 0" class="bg-ls-card rounded-lg border border-ls-border px-4 py-3 grid grid-cols-5 gap-4 text-xs mb-4 neon-glow">
        <div>
          <span class="text-ls-muted">输入 Token</span>
          <span class="block mt-1 text-base font-mono text-ls-text">{{ fmt(modelInfoTotalInput) }}</span>
        </div>
        <div>
          <span class="text-ls-muted">输出 Token</span>
          <span class="block mt-1 text-base font-mono text-ls-text">{{ fmt(modelInfoTotalOutput) }}</span>
        </div>
        <div>
          <span class="text-ls-muted">总 Token</span>
          <span class="block mt-1 text-base font-mono text-ls-text">{{ fmt(modelInfoTotalTokens) }}</span>
        </div>
        <div>
          <span class="text-ls-muted">缓存命中</span>
          <span class="block mt-1 text-base font-mono" :class="(modelInfoTotalCached || 0) > 0 ? 'text-green-400' : 'text-ls-muted'">{{ fmt(modelInfoTotalCached) }}</span>
        </div>
        <div>
          <span class="text-ls-muted">可用模型</span>
          <span class="block mt-1 text-base font-mono text-ls-text">{{ modelInfoAvailable }} / {{ modelInfoRows.length }}</span>
        </div>
      </div>

      <CTable v-if="modelInfoRows.length > 0" pad="sm">
        <thead>
          <tr>
            <th class="text-left">模型</th>
            <th class="text-left">类型</th>
            <th class="text-left">配额</th>
            <th class="text-right">输入</th>
            <th class="text-right">缓存命中</th>
            <th class="text-right">输出</th>
            <th class="text-left">窗口</th>
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
            <td class="text-right text-xs font-mono text-ls-dim">{{ (m.today_input_tokens || 0).toLocaleString() }}</td>
            <td class="text-right text-xs font-mono" :class="(m.today_cached_tokens || 0) > 0 ? 'text-green-400' : 'text-ls-muted'">{{ (m.today_cached_tokens || 0).toLocaleString() }}</td>
            <td class="text-right text-xs font-mono text-ls-dim">{{ (m.today_output_tokens || 0).toLocaleString() }}</td>
            <td class="text-xs">
              <span v-if="windowLabel(m)" class="text-ls-dim">
                <span :class="m.window_quota_remaining > 0 ? 'text-ls-text' : 'text-ls-muted'">{{ windowLabel(m).head }}</span>
                <span v-if="windowLabel(m).sub" class="text-ls-muted"> · {{ windowLabel(m).sub }}</span>
              </span>
              <span v-else class="text-ls-muted">—</span>
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
import IconButton from '@/components/IconButton.vue'
import CIcon from '@/components/CIcon.vue'
import FormField from '@/components/FormField.vue'
import ModelListEditor from '@/components/ModelListEditor.vue'
import CCheckbox from '@/components/CCheckbox.vue'
import CSelect from '@/components/CSelect.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import { maskKey, formatContextLength } from '@/utils/format'
import { modelTypeColor, modelTypeLabel } from '@/constants/modelType'
import { getSuppliers, createSupplier as apiCreateSupplier, updateSupplier as apiUpdateSupplier, deleteSupplier as apiDeleteSupplier, toggleSupplier as apiToggleSupplier, getSupplierModels, bulkSetSupplierModels as apiBulkSetSupplierModels, getModelQuotas, getProviderTypes } from '@/api'

const toast = inject('$toast')

// ── State ──
const loading = ref(true)
const error = ref(null)
const suppliers = ref([])
const activeCount = computed(() => suppliers.value.filter(a => a.status === 'active').length)

// ── 供应商类型（来自后端 provider_types，支持动态新增/配置） ──
const providerTypes = ref([])
const providerTypeOptions = computed(() =>
  providerTypes.value.map(pt => ({ label: pt.name, value: pt.type_key }))
)
const ptMap = computed(() =>
  Object.fromEntries(providerTypes.value.map(pt => [pt.type_key, pt]))
)
const providerTypeLabel = (t) => ptMap.value[t]?.name || t || '—'
const providerTypeColor = (t) => ptMap.value[t]?.color || '#89b4fa'

const loadProviderTypes = async () => {
  try {
    const res = await getProviderTypes()
    providerTypes.value = res.data || []
  } catch { /* 保留空列表，下拉将无选项 */ }
}

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
      today_cached_tokens: q.today_cached_tokens || 0,
      is_unavailable: q.is_unavailable || false,
      strategy_type: q.strategy_type || '',
      window_seconds: q.window_seconds || 0,
      window_quota_remaining: q.window_quota_remaining || 0,
      window_quota_limit: q.window_quota_limit || 0,
    }
  })
})

const MODEL_INFO_DAYS_OPTIONS = [
  { label: '今天', value: 0 },
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
]

// 模型用量抽屉的「窗口」列：展示按模型/固定窗口策略的剩余与上限
const windowLabel = (m) => {
  if (!m.strategy_type) return null
  const isPerModel = m.strategy_type === 'fixed_window_per_model'
  const secs = m.window_seconds || 0
  const val = secs >= 3600 ? `${secs / 3600}h` : `${secs / 60}m`
  const head = isPerModel ? `按模型 ${val}` : `固定窗口 ${val}`
  const rem = m.window_quota_remaining
  const max = m.window_quota_limit
  const sub = rem != null && max != null ? `${rem}/${max}` : (max != null ? `${max}` : '')
  return { head, sub }
}
const modelInfoDays = ref(0)
const fmt = (n) => (n || 0).toLocaleString()

const modelInfoTotalInput = computed(() =>
  modelInfoRows.value.reduce((s, m) => s + (m.today_input_tokens || 0), 0)
)
const modelInfoTotalOutput = computed(() =>
  modelInfoRows.value.reduce((s, m) => s + (m.today_output_tokens || 0), 0)
)
const modelInfoTotalTokens = computed(() => modelInfoTotalInput.value + modelInfoTotalOutput.value)
const modelInfoTotalCached = computed(() =>
  modelInfoRows.value.reduce((s, m) => s + (m.today_cached_tokens || 0), 0)
)
const modelInfoAvailable = computed(() =>
  modelInfoRows.value.filter(m => !m.is_unavailable).length
)

const openModelInfo = (acc) => {
  modelInfoSupplier.value = acc
  showModelInfoDrawer.value = true
}

// ── Add drawer ──
const showAddDrawer = ref(false)
const adding = ref(false)
const addNameInput = ref(null)
const newSupplier = ref({ name: '', api_key: '', base_url: '', provider_type: 'modelscope', models: [] })
const showNewApiKey = ref(false)

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
  newSupplier.value = { name: '', api_key: '', base_url: '', provider_type: 'modelscope', models: [] }
  showNewApiKey.value = false
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
      provider_type: newSupplier.value.provider_type,
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
    provider_type: acc.provider_type || 'modelscope',
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
      provider_type: editingSupplier.value.provider_type,
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
  loadProviderTypes()
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
