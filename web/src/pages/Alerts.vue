<template>
  <div>
    <PageHeader title="告警历史" subtitle="配额耗尽、请求失败等告警记录">
      <template #action>
        <div class="w-48">
          <CSelect v-model="alertFilter" :options="ALERT_TYPE_OPTIONS" size="sm" placeholder="全部类型" />
        </div>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">Loading...</div>
      </div>
      <div v-else>
      <!-- Summary cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-3.5 mb-6">
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">今日告警</p>
          <p class="text-2xl font-semibold tracking-tight text-white">7</p>
          <p class="text-xs text-gray-500 mt-1">较昨日 +2</p>
        </div>
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">本周告警</p>
          <p class="text-2xl font-semibold tracking-tight text-white">23</p>
          <p class="text-xs text-gray-500 mt-1">配额耗尽 18 · 请求失败 5</p>
        </div>
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">最近严重告警</p>
          <p class="text-2xl font-semibold tracking-tight text-white">—</p>
          <p class="text-xs text-green-400 mt-1">系统运行正常</p>
        </div>
      </div>

      <!-- Alert List -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border flex items-center justify-between">
          <h2 class="font-semibold tracking-tight text-sm">告警记录</h2>
          <span class="text-xs text-gray-500">共 {{ filteredAlerts.length }} 条</span>
        </div>
        <div>
          <div v-for="alert in filteredAlerts" :key="alert.id"
            class="px-5 py-3.5 border-b border-ls-border/50 flex items-start gap-3 hover:bg-ls-elevated transition-colors last:border-b-0">
            <span class="flex-shrink-0 mt-1">
              <svg v-if="alert.level === 'warning'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-yellow-400">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <svg v-else-if="alert.level === 'error'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-red-400">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              <svg v-else-if="alert.level === 'info'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-ls-accent">
                <circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/>
              </svg>
              <svg v-else-if="alert.level === 'critical'" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-red-400">
                <circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/>
              </svg>
              <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-green-400">
                <circle cx="12" cy="12" r="10"/><polyline points="9 12 11 14 15 10"/>
              </svg>
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm text-white">{{ alert.title }}</span>
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs" :class="levelClass(alert.level)">{{ levelLabel(alert.level) }}</span>
                <span class="text-xs text-gray-500 ml-auto">{{ alert.timestamp }}</span>
              </div>
              <p class="text-xs text-gray-400 mt-1">{{ alert.message }}</p>
            </div>
          </div>
        </div>
      </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import { getAlerts } from '@/api'
import CSelect from '@/components/CSelect.vue'

const ALERT_TYPE_OPTIONS = [
  { label: '全部类型', value: 'all' },
  { label: '配额耗尽', value: 'quota_exhausted' },
  { label: '请求失败', value: 'api_error' },
  { label: '供应商禁用', value: 'account_disabled' },
]

const alertFilter = ref('all')
const loading = ref(true)
const alerts = ref([])

const loadData = async () => {
  loading.value = true
  try {
    const res = await getAlerts(7)
    const list = res.data || []
    // Generate ID and map to our format
    alerts.value = list.map((a, i) => ({ id: i, ...a }))
  } catch (e) {
    console.error('Failed to load alerts:', e)
    alerts.value = []
  }
  loading.value = false
}

const filteredAlerts = computed(() => {
  if (alertFilter.value === 'all') return alerts.value
  return alerts.value.filter(a => a.type === alertFilter.value || a.level === alertFilter.value)
})

const levelClass = (level) => ({
  warning: 'bg-yellow-500/10 text-yellow-400',
  error: 'bg-red-500/10 text-red-400',
  info: 'bg-ls-accent/10 text-ls-accent',
  critical: 'bg-red-500/10 text-red-400',
  recovered: 'bg-green-500/10 text-green-400',
}[level] || 'bg-ls-elevated text-gray-400')

const levelLabel = (level) => ({
  warning: '警告', error: '错误', info: '信息', critical: '严重', recovered: '恢复',
}[level] || level)

onMounted(() => loadData())
</script>
