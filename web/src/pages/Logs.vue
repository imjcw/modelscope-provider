<template>
  <div>
    <PageHeader title="请求日志">
      <template #action>
        <button class="btn btn-primary">↻ 刷新</button>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else>
      <!-- Filters (2 rows) -->
      <div class="flex flex-wrap gap-3 mb-5">
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">时间</label>
          <input type="text" v-model="filters.startTime" placeholder="开始"
            class="bg-transparent text-sm text-white border-0 focus:outline-none w-24 placeholder:text-gray-600">
          <span class="text-gray-600 text-xs">~</span>
          <input type="text" v-model="filters.endTime" placeholder="结束"
            class="bg-transparent text-sm text-white border-0 focus:outline-none w-24 placeholder:text-gray-600">
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">供应商</label>
          <div class="w-36"><CSelect v-model="filters.accountId" :options="ACCOUNT_OPTIONS" size="sm" placeholder="选择供应商" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2 flex-1 min-w-[200px]">
          <label class="text-xs text-gray-500 flex-shrink-0">请求 ID</label>
          <input v-model="filters.requestId" type="text" placeholder="输入请求 ID"
            class="bg-transparent text-sm text-white placeholder:text-gray-600 border-0 focus:outline-none flex-1">
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">状态</label>
          <div class="w-20"><CSelect v-model="filters.statusCode" :options="STATUS_CODE_OPTIONS" size="sm" placeholder="全部" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">模型</label>
          <div class="w-36"><CSelect v-model="filters.model" :options="MODEL_OPTIONS" size="sm" placeholder="选择模型" /></div>
        </div>
        <div class="flex items-center gap-2 bg-ls-card rounded-lg border border-ls-border px-3 py-2">
          <label class="text-xs text-gray-500 flex-shrink-0">流式</label>
          <div class="w-20"><CSelect v-model="filters.isStream" :options="STREAM_OPTIONS" size="sm" placeholder="全部" /></div>
        </div>
      </div>

      <!-- Table -->
      <div v-if="filteredLogs.length === 0 && !loading" class="text-center text-gray-500 py-12">
        暂无日志记录
      </div>
      <div v-else class="bg-ls-card rounded-lg border border-ls-border overflow-hidden">
        <table class="w-full text-xs">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border bg-ls-bg">
              <th class="text-left px-4 py-2.5 font-medium">时间</th>
              <th class="text-left px-4 py-2.5 font-medium">请求 ID</th>
              <th class="text-left px-4 py-2.5 font-medium">模型</th>
              <th class="text-left px-4 py-2.5 font-medium">供应商</th>
              <th class="text-left px-4 py-2.5 font-medium">状态</th>
              <th class="text-left px-4 py-2.5 font-medium">输入 Token</th>
              <th class="text-left px-4 py-2.5 font-medium">输出 Token</th>
              <th class="text-left px-4 py-2.5 font-medium">延迟</th>
              <th class="text-left px-4 py-2.5 font-medium">流式</th>
              <th class="text-right px-4 py-2.5 font-medium">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="log in filteredLogs" :key="log.request_id"
              class="border-b border-ls-border/50 hover:bg-ls-elevated transition-colors cursor-pointer"
              @click="showDetail(log)">
              <td class="px-4 py-3 text-gray-400">{{ formatTime(log.timestamp) }}</td>
              <td class="px-4 py-3 text-gray-300 font-mono">{{ log.request_id }}</td>
              <td class="px-4 py-3">
                <span class="text-white hover:underline inline-flex items-center gap-1.5">
                  <span class="w-4 h-4 rounded bg-ls-elevated flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ log.model[0].toUpperCase() }}</span>
                  <span class="font-mono">{{ log.model }}</span>
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center gap-1.5 text-gray-400">
                  <span class="w-4 h-4 rounded bg-ls-elevated flex items-center justify-center text-[9px] font-bold text-ls-accent">{{ (log.account_name || log.account_id || '')[0].toUpperCase() }}</span>
                  {{ log.account_name || log.account_id }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                  :class="log.status_code >= 500 ? 'bg-red-500/10 text-red-400' : log.status_code >= 400 ? 'bg-yellow-500/10 text-yellow-400' : 'bg-green-500/10 text-green-400'">
                  {{ log.status_code }}
                </span>
              </td>
              <td class="px-4 py-3 font-mono text-white">{{ log.input_tokens.toLocaleString() }}</td>
              <td class="px-4 py-3 font-mono text-white">{{ log.output_tokens.toLocaleString() }}</td>
              <td class="px-4 py-3 font-mono text-white">{{ log.latency_ms }}ms</td>
              <td class="px-4 py-3">
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5"
                  :class="log.is_stream ? 'bg-ls-accent/10 text-ls-accent' : 'bg-ls-elevated text-gray-400'">
                  {{ log.is_stream ? 'P' : 'N' }}
                </span>
              </td>
              <td class="px-4 py-3 text-right">
                <button @click.stop="showDetail(log)" class="bg-ls-elevated text-gray-300 hover:text-white rounded-md px-3 py-1 text-xs transition-colors">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Pagination -->
      <div class="flex items-center justify-between mt-4">
        <p class="text-xs text-gray-500">共 {{ total }} 条记录</p>
        <div class="flex items-center gap-2">
          <button @click="page--" :disabled="page <= 0"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">← 上页</button>
          <span class="text-xs text-gray-500">{{ page + 1 }} / {{ totalPages }}</span>
          <button @click="page++" :disabled="page >= totalPages - 1"
            class="text-xs text-gray-400 hover:text-white px-2 py-1.5 rounded-md hover:bg-ls-card disabled:opacity-30">下页 →</button>
        </div>
      </div>

      <!-- Detail Panel -->
      <LogDetailPanel v-model="selectedLog" />
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { getLogs, getSuppliers, getSupplierModels } from '@/api'
import CSelect from '@/components/CSelect.vue'
import LogDetailPanel from './LogDetailPanel.vue'

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

const page = ref(0)
const pageSize = 20
const total = ref(0)
const totalPages = computed(() => Math.ceil(total.value / pageSize))
const loading = ref(true)

const logs = ref([])
const filters = ref({ model: '', accountId: '', statusCode: '', isStream: '' })

const filteredLogs = computed(() => {
  let r = [...logs.value]
  if (filters.value.model) r = r.filter(l => l.model === filters.value.model)
  if (filters.value.accountId) r = r.filter(l => l.account_id === filters.value.accountId)
  if (filters.value.statusCode) r = r.filter(l => l.status_code === Number(filters.value.statusCode))
  if (filters.value.isStream !== '' && filters.value.isStream !== undefined) r = r.filter(l => l.is_stream === filters.value.isStream)
  return r
})

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
