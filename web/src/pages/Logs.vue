<template>
  <div>
    <PageHeader title="请求日志" subtitle="查看、筛选和排查所有上游请求记录">
      <template #action>
        <div class="flex items-center gap-3">
          <!-- 定时刷新 -->
          <div class="flex bg-ls-card rounded-lg border border-ls-border p-0.5">
            <button v-for="opt in REFRESH_OPTIONS" :key="opt.label" type="button"
              @click="setRefresh(opt.ms)"
              class="px-2.5 h-8 rounded-md text-xs font-medium transition-colors"
              :class="refreshInterval === opt.ms
                ? 'bg-ls-elevated text-white'
                : 'text-gray-500 hover:text-white'">
              {{ opt.label }}
            </button>
          </div>
          <button @click="loadLogs()" class="btn btn-primary">↻ 刷新</button>
        </div>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading && logs.length === 0" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else>
      <!-- Filters (1 row) -->
      <div class="flex flex-wrap gap-3 mb-5 items-center">
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">时间</label>
          <div class="w-56"><DateRangePicker @update="onTimeChange" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">供应商</label>
          <div class="w-36"><CSelect v-model="filters.accountId" :options="ACCOUNT_OPTIONS" size="sm" placeholder="选择供应商" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">模型</label>
          <div class="w-36"><CSelect v-model="filters.model" :options="MODEL_OPTIONS" size="sm" placeholder="选择模型" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">状态</label>
          <div class="w-20"><CSelect v-model="filters.statusCode" :options="STATUS_CODE_OPTIONS" size="sm" placeholder="全部" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">流式</label>
          <div class="w-20"><CSelect v-model="filters.isStream" :options="STREAM_OPTIONS" size="sm" placeholder="全部" /></div>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           日志列表（表格）
           ═══════════════════════════════════════════ -->
      <div>
        <div v-if="filteredLogs.length === 0 && !loading" class="text-center text-gray-500 py-12">
          暂无日志记录
        </div>
        <div v-else class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
          <table class="w-full text-xs">
            <thead>
              <tr class="text-gray-500 border-b border-ls-border bg-ls-bg">
                <th class="text-left px-4 py-2.5 font-medium">时间</th>
                <th class="text-left px-4 py-2.5 font-medium">请求 ID</th>
                <th class="text-left px-4 py-2.5 font-medium">供应商</th>
                <th class="text-left px-4 py-2.5 font-medium">模型</th>
                <th class="text-left px-4 py-2.5 font-medium">状态</th>
                <th class="text-left px-4 py-2.5 font-medium">输入 Token</th>
                <th class="text-left px-4 py-2.5 font-medium">Cache 命中</th>
                <th class="text-left px-4 py-2.5 font-medium">输出 Token</th>
                <th class="text-left px-4 py-2.5 font-medium">延迟</th>
                <th class="text-left px-4 py-2.5 font-medium">流式</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in filteredLogs" :key="log.request_id"
                class="border-b border-ls-border/50 hover:bg-ls-elevated transition-colors cursor-pointer"
                @click="showDetail(log)">
                <td class="px-4 py-3 text-gray-400">{{ formatTime(log.timestamp) }}</td>
                <td class="px-4 py-3 text-gray-300 font-mono">{{ log.request_id }}</td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center gap-1.5 text-gray-400">
                    <span class="w-4 h-4 rounded bg-ls-elevated flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ (log.account_name || log.account_id || '')[0].toUpperCase() }}</span>
                    {{ log.account_name || log.account_id }}
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span class="text-white hover:underline inline-flex items-center gap-1.5">
                    <span class="w-4 h-4 rounded bg-ls-elevated flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ log.model[0].toUpperCase() }}</span>
                    <span class="font-mono">{{ log.model }}</span>
                  </span>
                </td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                    :class="log.status_code >= 500 ? 'bg-red-500/10 text-red-400' : log.status_code >= 400 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-green-500/10 text-green-400'">
                    {{ log.status_code }}
                  </span>
                </td>
                <td class="px-4 py-3 font-mono text-white">{{ (log.input_tokens || 0).toLocaleString() }}</td>
                <td class="px-4 py-3 font-mono"
                  :class="(log.cached_tokens || 0) + (log.prompt_partial_cached || 0) > 0 ? 'text-green-400' : 'text-gray-600'">
                  {{ ((log.cached_tokens || 0) + (log.prompt_partial_cached || 0)).toLocaleString() }}
                </td>
                <td class="px-4 py-3 font-mono text-white">{{ (log.output_tokens || 0).toLocaleString() }}</td>
                <td class="px-4 py-3 font-mono text-white">{{ log.latency_ms }}ms</td>
                <td class="px-4 py-3">
                  <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                    :class="log.is_stream ? 'bg-ls-accent/10 text-ls-accent' : 'bg-ls-elevated text-gray-400'">
                    {{ log.is_stream ? 'P' : 'N' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between mt-4">
        <p class="text-xs text-gray-500">共 {{ total }} 条记录</p>
        <div class="flex items-center gap-2">
          <button @click="page = 0" :disabled="page <= 0"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">⇤ 首页</button>
          <button @click="page--" :disabled="page <= 0"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">← 上页</button>
          <span class="text-xs text-gray-500">{{ page + 1 }} / {{ totalPages }}</span>
          <button @click="page++" :disabled="page >= totalPages - 1"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">下页 →</button>
          <button @click="page = totalPages - 1" :disabled="page >= totalPages - 1"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">末页 ⇥</button>
        </div>
      </div>

      <!-- Detail Panel -->
      <LogDetailPanel v-model="selectedLog" />
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
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
  { label: '关', ms: 0 },
  { label: '10s', ms: 10000 },
  { label: '30s', ms: 30000 },
  { label: '1m', ms: 60000 },
  { label: '5m', ms: 300000 },
]

const page = ref(0)
const pageSize = 20
const total = ref(0)
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
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
function onTimeChange({ start, end }) {
  filters.value.startTime = start
  filters.value.endTime = end
  page.value = 0
  loadLogs()
}

// 筛选已由后端完成，这里直接透出当前页数据
const filteredLogs = computed(() => logs.value)

const selectedLog = ref(null)

const formatTime = (ts) => {
  if (!ts) return ''
  // Treat the input as UTC (append Z)
  const d = new Date(ts.replace(' ', 'T') + 'Z')
  if (isNaN(d.getTime())) return ts
  // Manually compute UTC+8 components (avoid browser timezone dependency)
  const cst = new Date(d.getTime() + 8 * 3600000)
  const pad = (n, l = 2) => String(n).padStart(l, '0')
  // Use getUTC* to read the raw values, which now represent UTC+8
  return `${cst.getUTCFullYear()}-${pad(cst.getUTCMonth() + 1)}-${pad(cst.getUTCDate())} ${pad(cst.getUTCHours())}:${pad(cst.getUTCMinutes())}:${pad(cst.getUTCSeconds())}.${String(cst.getUTCMilliseconds()).padStart(3, '0')}`
}

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
  () => { page.value = 0; loadLogs() },
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
  loadLogs()
})
</script>
