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
        <FilterField label="时间" width="lg:w-56">
          <DateRangePicker :utc8="true" @update="onTimeChange" />
        </FilterField>
        <FilterField label="供应商" width="lg:w-36">
          <CSelect v-model="filters.accountId" :options="ACCOUNT_OPTIONS" size="sm" placeholder="选择供应商" />
        </FilterField>
        <FilterField label="模型" width="lg:w-36">
          <CSelect v-model="filters.model" :options="MODEL_OPTIONS" size="sm" placeholder="选择模型" />
        </FilterField>
        <FilterField label="状态" width="lg:w-20">
          <CSelect v-model="filters.statusCode" :options="STATUS_CODE_OPTIONS" size="sm" placeholder="全部" />
        </FilterField>
        <FilterField label="流式" width="lg:w-20">
          <CSelect v-model="filters.isStream" :options="STREAM_OPTIONS" size="sm" placeholder="全部" />
        </FilterField>
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
              <th class="text-left">请求 ID</th>
              <th class="text-left">供应商</th>
              <th class="text-left">模型</th>
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
              <td class="text-ls-dim font-mono">{{ log.request_id }}</td>
              <td>
                <span class="inline-flex items-center gap-1.5 text-ls-dim">
                  <span class="w-4 h-4 rounded bg-ls-accent/10 flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ (log.account_name || log.account_id || '')[0].toUpperCase() }}</span>
                  {{ log.account_name || log.account_id }}
                </span>
              </td>
              <td>
                <span class="text-ls-text hover:underline inline-flex items-center gap-1.5">
                  <span class="w-4 h-4 rounded bg-ls-accent/10 flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ log.model[0].toUpperCase() }}</span>
                  <span class="font-mono">{{ log.model }}</span>
                </span>
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
import LogDetailPanel from './LogDetailPanel.vue'
import DateRangePicker from '@/components/DateRangePicker.vue'

const ACCOUNT_OPTIONS = ref([
  { label: '选择供应商', value: '' },
])
const STATUS_CODE_OPTIONS = [
  { label: '全部', value: '' },
  { label: '200', value: '200' },
  { label: '429', value: '429' },
  { label: '500', value: '500' },
]
const MODEL_OPTIONS = ref([
  { label: '选择模型', value: '' },
])
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
const filters = ref({ model: '', accountId: '', statusCode: '', isStream: '', startTime: '', endTime: '' })

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

function onTimeChange({ start, end }) {
  filters.value.startTime = start
  filters.value.endTime = end
  resetAndLoad()
}

// 筛选已由后端完成，这里直接透出当前页数据
const filteredLogs = computed(() => logs.value)

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
    if (filters.value.startTime) params.start_time = filters.value.startTime
    if (filters.value.endTime) params.end_time = filters.value.endTime
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

// 非时间筛选变化时，回到第一页并重新加载
watch(
  () => [filters.value.model, filters.value.accountId, filters.value.statusCode, filters.value.isStream],
  () => resetAndLoad(),
)

const loadFilterOptions = async () => {
  try {
    const res = await getSuppliers()
    const sups = res.data || []
    ACCOUNT_OPTIONS.value = [
      { label: '选择供应商', value: '' },
      ...sups.map(s => ({ label: s.name || s.account_id, value: s.account_id || s.id })),
    ]
    // Collect all model names from all suppliers
    const modelNames = new Set()
    for (const s of sups) {
      try {
        const mRes = await getSupplierModels(s.id)
        ;(mRes.data || []).forEach(m => {
          if (m.model_name) modelNames.add(m.model_name)
        })
      } catch { /* skip */ }
    }
    MODEL_OPTIONS.value = [
      { label: '选择模型', value: '' },
      ...[...modelNames].sort().map(name => ({ label: name, value: name })),
    ]
  } catch { /* keep defaults */ }
}

onMounted(async () => {
  await loadFilterOptions()
  // 显式加载日志数据（DateRangePicker 的 mount emit 可能因时序问题未能触发首次加载）
  loadLogs()
})
</script>
