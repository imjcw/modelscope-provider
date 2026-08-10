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
                <div class="relative group/cb">
                  <p class="font-medium text-ls-text flex items-center gap-2">
                    {{ acc.name }}
                    <span v-if="cbByAccount[acc.id]?.length"
                      class="inline-flex items-center gap-1 text-[10px] px-1.5 py-0.5 rounded bg-red-500/15 text-red-400 border border-red-500/25 font-medium whitespace-nowrap"
                      :title="formatCircuitBreakerTooltip(acc.id)">
                      <span class="w-1.5 h-1.5 rounded-full bg-red-400 animate-pulse"></span>
                      熔断
                    </span>
                  </p>
                  <p class="text-xs text-ls-muted font-mono">{{ maskKey(acc.api_key) }}</p>
                  <p v-if="acc.api_keys && acc.api_keys.length > 1" class="text-xs text-ls-dim">
                    +{{ acc.api_keys.length - 1 }} 个密钥
                    <span v-if="acc.api_key_records && acc.api_key_records.some(r => r.status === 'frozen')"
                      class="text-yellow-400"> · 有已冻结密钥</span>
                    <span v-if="cbByAccount[acc.id]?.length"
                      class="text-red-400 font-medium">
                      · {{ cbByAccount[acc.id].length }} 个模型熔断中
                    </span>
                  </p>
                  <p v-else-if="cbByAccount[acc.id]?.length"
                    class="text-xs text-red-400 font-medium">
                    <CIcon name="alert-triangle" :size="11" :stroke-width="2.5" class="inline mr-1" />
                    {{ cbByAccount[acc.id].length }} 个模型被熔断器冻结
                  </p>
                </div>
              </div>
            </td>
            <td>
              <CCheckbox :model-value="acc.status === 'active'" @update:modelValue="(val) => toggleSupplier(val, acc)" />
            </td>
            <td class="text-xs" v-if="acc.provider_type">
              <span class="text-ls-text">{{ acc.quota_remaining }}</span>
              <span class="text-ls-muted"> / {{ acc.quota_limit }}</span>
            </td>
            <td class="text-xs text-ls-muted" v-else>—</td>
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
        <!-- ── 密钥管理（统一管理所有密钥） ── -->
        <FormField label="密钥管理">
          <div class="space-y-2">
            <div v-for="(record, idx) in newSupplier.api_key_records" :key="'new-' + idx"
              class="bg-ls-bg rounded-lg border border-ls-border p-3">
              <div class="grid grid-cols-1 md:grid-cols-[120px_1fr_auto_28px] gap-2 items-center">
                <input v-model="record.alias" type="text" placeholder="别名"
                  class="form-input h-10 px-2 text-sm w-full" />
                <div class="flex items-center gap-2">
                  <input v-if="record._showKey" v-model="record.api_key" type="text"
                    class="form-input h-10 px-3 font-mono text-sm flex-1" />
                  <div v-else
                    class="form-input h-10 px-3 font-mono text-sm flex-1 cursor-default select-none"
                    @click="toggleKeyVisibility(record)" :title="record.api_key">
                    {{ maskKey(record.api_key) }}
                  </div>
                  <button type="button" @click="toggleKeyVisibility(record)"
                    class="text-ls-muted hover:text-ls-text p-1 flex-shrink-0" :title="record._showKey ? '隐藏密钥' : '显示密钥'">
                    <CIcon :name="record._showKey ? 'eye-off' : 'eye'" :size="14" :stroke-width="2" />
                  </button>
                </div>
                <CCheckbox :model-value="record._enabled" @update:modelValue="(val) => record._enabled = val"
                  class="key-toggle" />
                <button type="button" @click="removeNewApiKeyRecord(idx)"
                  class="action-icon" title="删除">
                  <CIcon name="x" />
                </button>
              </div>
            </div>
            <button type="button" @click="addNewApiKeyRecord"
              class="mt-3 w-full h-10 rounded-lg border border-dashed border-ls-border text-ls-accent hover:text-ls-accentHover hover:border-ls-accent/30 transition-all flex items-center justify-center gap-2 text-sm">
              <CIcon name="plus" :size="16" />
              添加密钥
            </button>
          </div>
        </FormField>
        <FormField label="供应商类型">
          <CSelect v-model="newSupplier.provider_type" :options="providerTypeOptions" placeholder="选择供应商类型（可选）" />
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
        <!-- ── 密钥管理（统一管理所有密钥：主键 + 额外密钥） ── -->
        <FormField label="密钥管理">
          <div class="space-y-2">
            <div v-for="(record, idx) in editingSupplier.api_key_records" :key="record.id || 'new-' + idx"
              class="bg-ls-bg rounded-lg border border-ls-border p-3">
              <div class="grid grid-cols-1 md:grid-cols-[120px_1fr_auto_28px] gap-2 items-center">
                <input v-model="record.alias" type="text" placeholder="别名"
                  class="form-input h-10 px-2 text-sm w-full" />
                <div class="flex items-center gap-2">
                  <input v-if="record._showKey" v-model="record.api_key" type="text"
                    class="form-input h-10 px-3 font-mono text-sm flex-1" />
                  <div v-else
                    class="form-input h-10 px-3 font-mono text-sm flex-1 cursor-default select-none"
                    @click="toggleKeyVisibility(record)" :title="record.api_key">
                    {{ maskKey(record.api_key) }}
                  </div>
                  <button type="button" @click="toggleKeyVisibility(record)"
                    class="text-ls-muted hover:text-ls-text p-1 flex-shrink-0" :title="record._showKey ? '隐藏密钥' : '显示密钥'">
                    <CIcon :name="record._showKey ? 'eye-off' : 'eye'" :size="14" :stroke-width="2" />
                  </button>
                </div>
                <CCheckbox :model-value="record._enabled" @update:modelValue="(val) => record._enabled = val"
                  class="key-toggle" />
                <button type="button" @click="deleteEditKey(record.id, idx)"
                  class="action-icon" title="删除此密钥">
                  <CIcon name="x" />
                </button>
              </div>
            </div>
            <div class="flex items-center gap-2 mt-3">
              <button type="button" @click="addEditApiKeyRecord"
                class="btn btn-secondary text-xs">
                <CIcon name="plus" :size="14" :stroke-width="2" class="mr-1" />
                添加密钥
              </button>
            </div>
          </div>
        </FormField>
        <FormField label="供应商类型">
          <CSelect v-model="editingSupplier.provider_type" :options="providerTypeOptions" placeholder="选择供应商类型（可选）" />
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

    <!-- ── 删除密钥确认 弹窗 ── -->
    <ConfirmModal
      v-model="showKeyDeleteModal"
      title="确认删除密钥"
      :message="`确定要删除密钥 <strong class='text-ls-text'>${pendingKeyDelete?.name || ''}</strong> 吗？<br><span class='text-ls-muted text-xs'>此操作不可撤销</span>`"
      danger
      @confirm="confirmKeyDelete"
    />

    <!-- ── 模型用量详情 抽屉 ── -->
    <Drawer v-model="showModelInfoDrawer" :title="`${modelInfoSupplier?.name || ''} · 模型用量`" width="1080px">
      <!-- 时间范围 + 按 key 筛选 -->
      <div class="flex items-center justify-between mb-4 flex-wrap gap-2">
        <div class="flex items-center gap-3 flex-wrap">
          <span class="text-xs text-ls-muted">
            共 {{ modelInfoRows.length }} 个模型
          </span>
          <div v-if="modelInfoSupplier?.api_key_records && modelInfoSupplier.api_key_records.length >= 1"
               class="flex items-center gap-1">
            <span class="text-xs text-ls-muted whitespace-nowrap">按 Key</span>
            <CSelect v-model="modelInfoKeyFilter"
                     :options="keyFilterOptions"
                     placeholder="全部 Key"
                     size="sm"
                     class="w-40" />
          </div>
        </div>
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
            <th class="text-center">配额</th>
            <th class="text-right">输入</th>
            <th class="text-right">缓存命中</th>
            <th class="text-right">输出</th>
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
            <td class="text-center">
              <div class="flex items-center justify-center gap-1.5 mb-1">
                <span class="text-xs px-2 py-0.5 rounded-full border font-medium"
                      :class="WINDOW_BADGE[fmtWindowRow(m).badge]">
                  {{ fmtWindowRow(m).label }}
                </span>
              </div>
              <div v-if="fmtWindowRow(m).sub" class="text-[10px] text-ls-muted mb-1">{{ fmtWindowRow(m).sub }}</div>
              <div v-if="usedPctRow(m) !== null" class="w-20 mx-auto">
                <ProgressBar :pct="usedPctRow(m)" width="w-20" height="h-1.5" :bar-class="barClass(usedPctRow(m))" />
              </div>
            </td>
            <td class="text-right text-xs font-mono text-ls-dim">{{ (m.today_input_tokens || 0).toLocaleString() }}</td>
            <td class="text-right text-xs font-mono" :class="(m.today_cached_tokens || 0) > 0 ? 'text-green-400' : 'text-ls-muted'">{{ (m.today_cached_tokens || 0).toLocaleString() }}</td>
            <td class="text-right text-xs font-mono text-ls-dim">{{ (m.today_output_tokens || 0).toLocaleString() }}</td>
            <td class="text-center">
              <template v-if="m.is_unavailable">
                <span class="tag tag-danger">不可用</span>
              </template>
              <template v-else-if="m.success_rate !== null && m.success_rate < 85">
                <span class="tag tag-warning">异常 {{ m.success_rate }}%</span>
              </template>
              <template v-else>
                <span class="tag tag-success">正常{{ m.success_rate !== null ? ' ' + m.success_rate + '%' : '' }}</span>
              </template>
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
import { ref, computed, watch, onMounted, nextTick, inject } from 'vue'
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
import ProgressBar from '@/components/ProgressBar.vue'
import { maskKey, formatContextLength } from '@/utils/format'
import { modelTypeColor, modelTypeLabel } from '@/constants/modelType'
import { getSuppliers, createSupplier as apiCreateSupplier, updateSupplier as apiUpdateSupplier, deleteSupplier as apiDeleteSupplier, toggleSupplier as apiToggleSupplier, getSupplierModels, bulkSetSupplierModels as apiBulkSetSupplierModels, deleteSupplierModel as apiDeleteSupplierModel, getModelQuotas, getProviderTypes, listApiKeys, addApiKey, updateApiKeyStatus, deleteApiKey, getCircuitBreakerStates } from '@/api'

const toast = inject('$toast')

// ── State ──
const loading = ref(true)
const error = ref(null)
const suppliers = ref([])
const activeCount = computed(() => suppliers.value.filter(a => a.status === 'active').length)

// ── 供应商类型（来自后端 provider_types，支持动态新增/配置） ──
const providerTypes = ref([])
const providerTypeOptions = computed(() =>
  [{ label: '无', value: '' }, ...providerTypes.value.map(pt => ({ label: pt.name, value: pt.type_key }))]
)
const ptMap = computed(() =>
  Object.fromEntries(providerTypes.value.map(pt => [pt.type_key, pt]))
)
const providerTypeLabel = (t) => ptMap.value[t]?.name || t || '—'
const providerTypeColor = (t) => ptMap.value[t]?.color || 'var(--chart-blue)'

const loadProviderTypes = async () => {
  try {
    const res = await getProviderTypes()
    providerTypes.value = res.data || []
  } catch { /* 保留空列表，下拉将无选项 */ }
}

// ── 模型用量数据（/api/model-quota） ──
const modelQuotaMap = ref({}) // { [supplier_id]: [quotaItems] }
const circuitBreakerStates = ref([]) // { key_id, account_id, model_name, frozen_remaining, error_type, ... }
const cbByAccount = computed(() => {
  const map = {}
  for (const s of circuitBreakerStates.value) {
    const aid = s.account_id
    if (!map[aid]) map[aid] = []
    map[aid].push(s)
  }
  return map
})
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
      success_rate: q.success_rate ?? null,
      request_count: q.request_count || 0,
      success_count: q.success_count || 0,
      strategy_type: q.strategy_type || '',
      window_seconds: q.window_seconds || 0,
      window_quota_remaining: q.window_quota_remaining || 0,
      window_quota_limit: q.window_quota_limit || 0,
      max_requests: q.max_requests ?? null,
      has_custom_window: q.has_custom_window || false,
    }
  })
})

const MODEL_INFO_DAYS_OPTIONS = [
  { label: '今天', value: 0 },
  { label: '7天', value: 7 },
  { label: '30天', value: 30 },
  { label: '90天', value: 90 },
]

// 模型用量抽屉的「配额」列：复用「用量分析」中 ModelStatusTable「限流」列样式
// （窗口 badge + 已用/上限滑窗 + 进度条），窗口配额优先，token 配额作为兜底。
const WINDOW_BADGE = {
  accent: 'bg-ls-accent/10 text-ls-accent border-ls-accent/20',
  muted: 'bg-ls-muted/10 text-ls-muted border-ls-border',
}
const barClass = (pct) =>
  pct < 50 ? 'bg-green-400' : pct < 90 ? 'bg-yellow-400' : 'bg-red-400'

const fmtWindowRow = (m) => {
  const st = m.strategy_type
  if (!st || st === 'header_based') return { label: '无限制', sub: '', badge: 'muted', custom: false }
  const secs = m.window_seconds || 0
  const val = secs >= 3600 ? (secs / 3600) : (secs / 60)
  const unit = secs >= 3600 ? 'h' : 'm'
  const max = m.max_requests ?? m.window_quota_limit ?? null
  const rem = m.window_quota_remaining
  const used = max != null && rem != null ? Math.max(0, max - rem) : null
  const sub = used != null ? `已用 ${used}/${max} 滑窗` : max != null ? `${max} 滑窗` : ''
  if (st === 'fixed_window_per_model')
    return { label: `按模型 ${val}${unit}`, sub, badge: 'accent', custom: !!m.has_custom_window }
  if (st === 'fixed_window' || st === 'sensetime')
    return { label: `滑动窗口 ${val}${unit}`, sub, badge: 'accent', custom: false }
  return { label: '被动', sub: '', badge: 'muted', custom: false }
}
const usedPctRow = (m) => {
  const winLimit = m.window_quota_limit
  const winRem = m.window_quota_remaining
  const limit = (winLimit != null ? winLimit : m.quota_limit) || 0
  const remaining = (winLimit != null ? winRem : m.quota_remaining) || 0
  return limit > 0 ? Math.round(((limit - remaining) / limit) * 100) : null
}
const modelInfoDays = ref(0)
const keyFilterOptions = computed(() => {
  const records = modelInfoSupplier.value?.api_key_records || []
  return [
    { label: '全部 Key', value: null },
    ...records.map(k => ({ label: k.alias || maskKey(k.api_key), value: k.id })),
  ]
})
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

const formatCircuitBreakerTooltip = (accountId) => {
  const states = cbByAccount.value[accountId] || []
  if (states.length === 0) return ''
  return states.map(s =>
    `${s.model_name} (${s.error_type || 'error'}) — 剩余 ${formatCircuitBreakerTime(s.frozen_remaining || 0)}`
  ).join('\n')
}

const formatCircuitBreakerTime = (seconds) => {
  if (seconds <= 0) return '已解冻'
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`
  return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
}

const openModelInfo = (acc) => {
  modelInfoSupplier.value = acc
  modelInfoKeyFilter.value = null
  showModelInfoDrawer.value = true
  loadModelQuotas(modelInfoDays.value, null)
}

// ── Add drawer ──
const showAddDrawer = ref(false)
const adding = ref(false)
const addNameInput = ref(null)
const newSupplier = ref({ name: '', api_key: '', base_url: '', provider_type: '', models: [], api_key_records: [] })

// ── Edit drawer ──
const showEditDrawer = ref(false)
const saving = ref(false)
const editingSupplier = ref(null)
const apiKeyLoading = ref(false)

// ── API Key management ──
const loadApiKeys = async (supplierId) => {
  try {
    const res = await listApiKeys(supplierId)
    return res.data || []
  } catch (e) {
    console.error('Failed to load API keys:', e)
    toast('加载密钥列表失败，将使用缓存数据', 'warning')
    return []
  }
}

const freezeApiKey = async (keyId) => {
  apiKeyLoading.value = true
  try {
    await updateApiKeyStatus(editingSupplier.value.id, keyId, { status: 'frozen' })
    await refreshApiKeyRecords()
  } catch (e) {
    toast('冻结失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    apiKeyLoading.value = false
  }
}

const unfreezeApiKey = async (keyId) => {
  apiKeyLoading.value = true
  try {
    await updateApiKeyStatus(editingSupplier.value.id, keyId, { status: 'active' })
    await refreshApiKeyRecords()
  } catch (e) {
    toast('解冻失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    apiKeyLoading.value = false
  }
}

const deleteApiKeyRecord = async (keyId) => {
  const record = editingSupplier.value.api_key_records.find(r => r.id === keyId)
  pendingKeyDelete.value = {
    keyId,
    name: record?.alias || maskKey(record?.api_key || ''),
  }
  showKeyDeleteModal.value = true
}

const confirmKeyDelete = async () => {
  if (!pendingKeyDelete.value) return
  apiKeyLoading.value = true
  try {
    await deleteApiKey(editingSupplier.value.id, pendingKeyDelete.value.keyId)
    await refreshApiKeyRecords()
    showKeyDeleteModal.value = false
    pendingKeyDelete.value = null
  } catch (e) {
    toast('删除失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
  } finally {
    apiKeyLoading.value = false
  }
}

const refreshApiKeyRecords = async () => {
  if (!editingSupplier.value) return
  const records = await loadApiKeys(editingSupplier.value.id)
  editingSupplier.value.api_key_records = records.map(r => ({
    ...r,
    _enabled: r.status !== 'frozen',
    _showKey: false,
  }))
}

const addNewApiKeyRecord = () => {
  newSupplier.value.api_key_records.push({ alias: '', api_key: '', _enabled: true, _showKey: false })
}

const addEditApiKeyRecord = () => {
  editingSupplier.value.api_key_records.push({ id: 0, alias: '', api_key: '', _enabled: true, _showKey: false })
}

const deleteEditKey = (keyId, idx) => {
  if (keyId && keyId !== 0) {
    deleteApiKeyRecord(keyId)
  } else {
    editingSupplier.value.api_key_records.splice(idx, 1)
  }
}

const toggleKeyVisibility = (record) => {
  record._showKey = !record._showKey
}

const removeNewApiKeyRecord = (idx) => {
  newSupplier.value.api_key_records.splice(idx, 1)
}

// ── Key delete confirmation modal ──
const showKeyDeleteModal = ref(false)
const pendingKeyDelete = ref(null) // { keyId, name }

// ── Delete confirmation modal ──
const showDeleteModal = ref(false)
const deleting = ref(false)
const deletingSupplier = ref(null)

// ── Model delete confirmation modal ──
const showModelDeleteModal = ref(false)
const pendingModelDelete = ref(null) // { name, source: 'new'|'edit', idx, id }

const confirmModelDelete = async () => {
  if (!pendingModelDelete.value) return
  const { source, idx, id } = pendingModelDelete.value
  // 已保存到数据库的模型：调用后端 API 真实删除（级联清理路由绑定）。
  // 此前只做 splice，保存走 bulk_upsert（纯 upsert 不删行），刷新后模型会"复活"。
  if (source === 'edit' && id) {
    try {
      await apiDeleteSupplierModel(editingSupplier.value.id, id)
      editingSupplier.value.models.splice(idx, 1)
      toast('模型已删除', 'success')
    } catch (e) {
      toast('删除失败: ' + (e.response?.data?.detail || e.message || ''), 'error')
      return
    }
  } else if (source === 'new') {
    newSupplier.value.models.splice(idx, 1)
  } else {
    editingSupplier.value.models.splice(idx, 1)
  }
  pendingModelDelete.value = null
  showModelDeleteModal.value = false
}

const openModelDeleteConfirm = (source, idx) => {
  const model = source === 'new'
    ? newSupplier.value.models[idx]
    : editingSupplier.value.models[idx]
  pendingModelDelete.value = { name: model?.model_name || '(未命名)', source, idx, id: model?.id || null }
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
    // Load model-level quotas (今日) and group by supplier_id
    await loadModelQuotas(0)
    await loadCircuitBreaker()
  } catch (e) {
    error.value = e.message || 'Failed to load suppliers'
  }
  loading.value = false
}

// ── 模型用量数据加载（支持时间范围 + 按 key 筛选） ──
const modelInfoKeyFilter = ref(null) // account_api_keys.id；null = 全部 key
const loadModelQuotas = async (days = 0, keyId = null) => {
  try {
    const mqRes = await getModelQuotas(days, keyId)
    const map = {}
    for (const mq of (mqRes.data || [])) {
      if (!map[mq.supplier_id]) map[mq.supplier_id] = []
      map[mq.supplier_id].push(mq)
    }
    modelQuotaMap.value = map
  } catch (e) {
    console.error('Failed to load model quotas:', e)
  }
}

// ── Circuit Breaker ──
const loadCircuitBreaker = async () => {
  try {
    const res = await getCircuitBreakerStates()
    circuitBreakerStates.value = res.data?.circuits || []
  } catch (e) {
    console.error('Failed to load circuit breaker states:', e)
  }
}

// 时间范围变化时重新加载模型用量数据
watch(modelInfoDays, (days) => {
  if (showModelInfoDrawer.value) loadModelQuotas(days)
})
watch(modelInfoKeyFilter, () => {
  if (showModelInfoDrawer.value) loadModelQuotas(modelInfoDays.value, modelInfoKeyFilter.value)
})

// ── Add (drawer) ──
const openAdd = async () => {
  newSupplier.value = { name: '', api_key: '', base_url: '', provider_type: '', models: [], api_key_records: [] }
  showAddDrawer.value = true
  await nextTick()
  addNameInput.value?.focus()
}

const closeAdd = () => {
  showAddDrawer.value = false
}

const addSupplier = async () => {
  const records = newSupplier.value.api_key_records.filter(r => r.api_key)
  if (!newSupplier.value.name || records.length === 0) {
    toast('请填写别名和 API Key', 'error')
    return
  }
  adding.value = true
  try {
    // Mark the primary key; keep user-supplied alias, only default to '主密钥' when empty
    const normalized = records.map((r, i) => ({
      alias: r.alias || (i === 0 ? '主密钥' : ''),
      api_key: r.api_key,
      status: r._enabled ? 'active' : 'frozen',
    }))
    const res = await apiCreateSupplier({
      name: newSupplier.value.name,
      base_url: newSupplier.value.base_url,
      provider_type: newSupplier.value.provider_type,
      api_key_records: normalized,
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
    provider_type: acc.provider_type || '',
    status: acc.status,
    models: [],
    api_key_records: acc.api_key_records || [],
  }
  try {
    const res = await getSupplierModels(acc.id)
    editingSupplier.value.models = res.data || []
  } catch (e) {
    console.error('Failed to load supplier models:', e)
  }
  // Load full API key records for status management
  const records = await loadApiKeys(acc.id)
  editingSupplier.value.api_key_records = records.map(r => ({
    ...r,
    _enabled: r.status !== 'frozen',
    _showKey: false,
  }))
  showEditDrawer.value = true
}

const closeEdit = () => {
  showEditDrawer.value = false
}

const saveEdit = async () => {
  if (!editingSupplier.value) return
  saving.value = true
  try {
    // Reload API keys if they appear missing to prevent accidental key loss.
    // This handles the case where loadApiKeys() failed when the edit drawer opened.
    if (!editingSupplier.value.api_key_records || editingSupplier.value.api_key_records.length === 0) {
      const freshRecords = await loadApiKeys(editingSupplier.value.id)
      editingSupplier.value.api_key_records = freshRecords.map(r => ({
        ...r,
        _enabled: r.status !== 'frozen',
        _showKey: false,
      }))
    }
    const records = []
    for (const r of editingSupplier.value.api_key_records) {
      if (r.api_key) {
        records.push({
          alias: r.alias || '',
          api_key: r.api_key,
          status: r._enabled ? 'active' : 'frozen',
        })
      }
    }
    const body = {
      name: editingSupplier.value.name,
      api_key: editingSupplier.value.api_key,
      base_url: editingSupplier.value.base_url,
      provider_type: editingSupplier.value.provider_type,
      status: editingSupplier.value.status,
      api_key_records: records,
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
/* ── 密钥行 toggle 缩小 ── */
.key-toggle .c-toggle {
  width: 28px !important;
  height: 16px !important;
  border-radius: 8px !important;
}
.key-toggle .c-toggle-thumb {
  width: 14px !important;
  height: 14px !important;
}
.key-toggle .c-toggle-checked .c-toggle-thumb {
  left: 14px !important;
}

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
