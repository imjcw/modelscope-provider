<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="请求日志 // Logs" subtitle="// 查看、筛选和排查所有上游请求记录">
      <template #action>
        <div class="flex items-center gap-3">
          <!-- 定时刷新 -->
          <SegmentedControl :model-value="refreshInterval" :options="REFRESH_OPTIONS"
            @update:model-value="setRefresh" />
          <button @click="loadLogs()" class="btn btn-primary">↻ 刷新</button>
        </div>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6">
      <PageState :loading="loading && logs.length === 0">
      <!-- Filters (1 row) -->
      <div class="flex flex-wrap gap-3 mb-5 items-center">
        <FilterField label="" width="lg:w-96">
          <CLevelSelect
            v-model:level1-model-value="filters.accountId"
            v-model:level2-model-value="filters.model"
            :level1-options="ACCOUNT_OPTIONS"
            :level2-options="supplierModelsMap"
            level1-placeholder="供应商"
            level2-placeholder="模型"
          />
        </FilterField>
        <FilterField label="状态" width="lg:w-20">
          <CSelect v-model="filters.statusCode" :options="STATUS_CODE_OPTIONS" size="sm" placeholder="全部" />
        </FilterField>
        <FilterField label="流式" width="lg:w-20">
          <CSelect v-model="filters.isStream" :options="STREAM_OPTIONS" size="sm" placeholder="全部" />
        </FilterField>

        <!-- 清除筛选 -->
        <button v-if="hasActiveFilters"
          @click="clearFilters"
          class="h-8 inline-flex items-center gap-1.5 px-3 rounded-lg border border-ls-border text-xs text-ls-muted hover:text-ls-text hover:border-ls-accent hover:bg-ls-elevated transition-colors">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
            stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
          清除
        </button>
      </div>

      <!-- ═══════════════════════════════════════════
           日志列表（表格）
           ═══════════════════════════════════════════ -->
      <div>
        <div v-if="filteredLogs.length === 0 && !loading" class="text-center text-ls-muted py-12">
          暂无日志记录
        </div>
        <CTable v-else size="sm" head-bg hover="full">
          <thead>
            <tr>
              <th class="text-left">时间</th>
              <th class="text-left">供应商</th>
              <th class="text-left">模型</th>
              <th class="text-left">路由</th>
              <th class="text-left">状态</th>
              <th class="text-left">输入</th>
              <th class="text-left">缓存命中</th>
              <th class="text-left">输出</th>
              <th class="text-left">延迟</th>
              <th class="text-left">流式</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in filteredLogs" :key="log.request_id"
              class="cursor-pointer" @click="showDetail(log)">
              <td class="text-ls-dim">{{ formatLogTime(log.timestamp) }}</td>
              <td>
                <span class="inline-flex items-center gap-1.5 text-ls-dim">
                  <span class="w-4 h-4 rounded bg-ls-accent/10 flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ (log.account_name || log.account_id || '')[0].toUpperCase() }}</span>
                  {{ log.account_name || log.account_id }}
                </span>
              </td>
              <td>
                <span class="text-ls-text hover:underline inline-flex items-center gap-1.5">
                  <span class="w-4 h-4 rounded bg-ls-accent/10 flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ (log.actual_model_id || log.model || '')[0].toUpperCase() }}</span>
                  <span class="font-mono truncate inline-block max-w-[180px]" :title="log.actual_model_id || log.model">{{ log.actual_model_id || log.model }}</span>
                </span>
              </td>
              <td>
                <span class="font-mono text-ls-dim truncate inline-block max-w-[140px]" :title="log.model">{{ log.model }}</span>
              </td>
              <td>
                <StatusCodeBadge :code="log.status_code" />
              </td>
              <td class="font-mono text-ls-text">{{ (log.input_tokens || 0).toLocaleString() }}</td>
              <td class="font-mono"
                :class="(log.cached_tokens || 0) + (log.prompt_partial_cached || 0) > 0 ? 'text-green-400' : 'text-ls-muted'">
                {{ ((log.cached_tokens || 0) + (log.prompt_partial_cached || 0)).toLocaleString() }}
              </td>
              <td class="font-mono text-ls-text">{{ (log.output_tokens || 0).toLocaleString() }}</td>
              <td class="font-mono text-ls-text">{{ log.latency_ms }}ms</td>
              <td>
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                  :class="log.is_stream ? 'bg-ls-accent/10 text-ls-accent' : 'bg-ls-elevated text-ls-dim'">
                  {{ log.is_stream ? 'P' : 'N' }}
                </span>
              </td>
            </tr>
          </tbody>
        </CTable>
      </div>

      <!-- Pagination -->
      <Pagination v-model:page="page" :total="total" :page-size="pageSize" />

      <!-- Detail Panel -->
      <LogDetailPanel v-model="selectedLog" />
    </PageState>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import FilterField from '@/components/FilterField.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import CTable from '@/components/CTable.vue'
import StatusCodeBadge from '@/components/StatusCodeBadge.vue'
import Pagination from '@/components/Pagination.vue'
import { formatTime } from '@/utils/format'
import { getLogs, getSuppliers, getSupplierModels } from '@/api'
import CSelect from '@/components/CSelect.vue'
import CLevelSelect from '@/components/CLevelSelect.vue'
import LogDetailPanel from './LogDetailPanel.vue'

const ACCOUNT_OPTIONS = ref([
  { label: '选择供应商', value: '' },
])
const supplierModelsMap = ref({}) // { supplierId: [{ label, value }], '' : [{ label, value }] }
const STATUS_CODE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '200', value: '200' },
  { label: '429', value: '429' },
  { label: '500', value: '500' },
]
const STREAM_OPTIONS = [
  { label: '全部', value: '' },
  { label: '是', value: true },
  { label: '否', value: false },
]

const REFRESH_OPTIONS = [
  { label: '关', value: 0 },
  { label: '10s', value: 10000 },
  { label: '30s', value: 30000 },
  { label: '1m', value: 60000 },
  { label: '5m', value: 300000 },
]

const page = ref(0)
const pageSize = 20
const total = ref(0)
const loading = ref(true)

const logs = ref([])
const filters = ref({ model: '', accountId: '', statusCode: '', isStream: '' })

// ── 定时刷新 ──
const refreshInterval = ref(0)
let refreshTimer = null
function setRefresh(ms) {
  refreshInterval.value = ms
  if (refreshTimer) { clearInterval(refreshTimer); refreshTimer = null }
  if (ms > 0) refreshTimer = setInterval(() => loadLogs(), ms)
}
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })

// ── 时间范围 ──
// 重置到第一页并加载：page 已为 0 时 watch(page) 不会触发，需手动加载，避免重复请求
function resetAndLoad() {
  if (page.value !== 0) page.value = 0 // 触发 watch(page) → loadLogs
  else loadLogs()
}

// 筛选已由后端完成，这里直接透出当前页数据
const filteredLogs = computed(() => logs.value)

// ── 清空筛选 ──
const hasActiveFilters = computed(() =>
  !!filters.value.accountId ||
  !!filters.value.model ||
  !!filters.value.statusCode ||
  (filters.value.isStream !== '' && filters.value.isStream !== undefined),
)

const clearFilters = () => {
  filters.value.accountId = ''
  filters.value.model = ''
  filters.value.statusCode = ''
  filters.value.isStream = ''
  resetAndLoad()
}

const selectedLog = ref(null)

// 日志时间戳按 UTC 存储，统一以 UTC+8 + 毫秒精度展示
const formatLogTime = (ts) => formatTime(ts, { utc8: true, ms: true })

const loadLogs = async () => {
  loading.value = true
  try {
    const params = { page: page.value, page_size: pageSize }
    if (filters.value.model) params.model = filters.value.model
    if (filters.value.accountId) params.account_id = filters.value.accountId
    if (filters.value.statusCode) params.status_code = filters.value.statusCode
    if (filters.value.isStream !== '' && filters.value.isStream !== undefined) params.is_stream = filters.value.isStream
    const res = await getLogs(params)
    logs.value = res.data.records || []
    total.value = res.data.total || 0
  } catch (e) {
    console.error('Failed to load logs:', e)
  }
  loading.value = false
}

const showDetail = (log) => {
  selectedLog.value = log
}

watch(page, () => loadLogs())

// 防抖变量（非时间筛选变化时延迟加载，避免级联选择连续触发）
let filterDebounceTimer = null

// 非时间筛选变化时，回到第一页并重新加载
watch(
  () => [filters.value.model, filters.value.accountId, filters.value.statusCode, filters.value.isStream],
  () => {
    if (filterDebounceTimer) clearTimeout(filterDebounceTimer)
    filterDebounceTimer = setTimeout(resetAndLoad, 300)
  },
)

const loadFilterOptions = async () => {
  try {
    const res = await getSuppliers()
    const sups = res.data || []
    ACCOUNT_OPTIONS.value = [
      { label: '选择供应商', value: '' },
      ...sups.map(s => ({ label: s.name || s.account_id, value: s.account_id || s.id })),
    ]
    // Build supplier → models map, plus a '' key for "all models"
    const allModelNames = new Set()
      const map = {}
    for (const s of sups) {
      try {
        const mRes = await getSupplierModels(s.id)
        const names = new Set((mRes.data || []).map(m => m.model_name).filter(Boolean))
        const arr = [...names].sort().map(name => ({ label: name, value: name }))
        map[s.account_id || s.id] = arr
        for (const n of names) allModelNames.add(n)
      } catch { /* skip */ }
    }
    map[''] = [...allModelNames].sort().map(name => ({ label: name, value: name }))
    supplierModelsMap.value = map
  } catch { /* keep defaults */ }
}

onMounted(async () => {
  await loadFilterOptions()
  loadLogs()
})
</script>
