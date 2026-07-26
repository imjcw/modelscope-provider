<template>
  <div class="h-full flex flex-col overflow-hidden">
    <PageHeader title="告警历史 // Alerts" subtitle="// 配额耗尽、请求失败等告警记录">
      <template #action>
        <div class="flex items-center gap-3">
          <ViewToggle v-model="viewMode" />
          <div class="w-48">
            <CSelect v-model="alertFilter" :options="ALERT_TYPE_OPTIONS" size="sm" placeholder="全部类型" />
          </div>
        </div>
      </template>
    </PageHeader>

    <div class="flex-1 overflow-y-auto min-h-0 px-6 md:px-8 py-6">
      <PageState :loading="loading">
      <!-- Summary cards -->
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard label="今日告警" :value="String(stats.today)" :sub="stats.todaySub" />
        <StatCard label="近 7 日告警" :value="String(stats.week)" :sub="stats.weekSub" />
        <StatCard label="最近严重告警" :value="stats.severeValue" :sub="stats.severeSub" :sub-class="stats.severeSubClass" />
      </div>

      <!-- ═══════════════════════════════════════════
           视图 1：卡片行（默认）
           ═══════════════════════════════════════════ -->
      <CCard v-if="viewMode === 'row'" title="告警记录" no-padding>
        <template #action>
          <span class="text-xs text-ls-muted">共 {{ filteredAlerts.length }} 条</span>
        </template>
        <div>
          <div v-for="alert in filteredAlerts" :key="alert.id"
            class="px-5 py-3.5 border-b border-ls-border/50 flex items-start gap-3 hover:bg-ls-elevated transition-colors last:border-b-0">
            <span class="flex-shrink-0 mt-1">
              <AlertLevelIcon :level="alert.level" />
            </span>
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-sm text-ls-text">{{ alert.title }}</span>
                <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs" :class="levelClass(alert.level)">{{ levelLabel(alert.level) }}</span>
                <span class="text-xs text-ls-muted ml-auto">{{ alert.timestamp }}</span>
              </div>
              <p class="text-xs text-ls-dim mt-1">{{ alert.message }}</p>
            </div>
          </div>
        </div>
      </CCard>

      <!-- ═══════════════════════════════════════════
           视图 2：网格卡片
           ═══════════════════════════════════════════ -->
      <div v-else-if="viewMode === 'grid'" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <div v-for="alert in filteredAlerts" :key="alert.id"
          class="bg-ls-card rounded-lg border border-ls-border p-4 hover:border-ls-dim/50 transition-all flex flex-col gap-2 neon-glow">
          <div class="flex items-center gap-2">
            <span class="flex-shrink-0">
              <AlertLevelIcon :level="alert.level" />
            </span>
            <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs" :class="levelClass(alert.level)">{{ levelLabel(alert.level) }}</span>
            <span class="text-xs text-ls-muted ml-auto">{{ alert.timestamp }}</span>
          </div>
          <p class="text-sm text-ls-text">{{ alert.title }}</p>
          <p class="text-xs text-ls-dim line-clamp-2">{{ alert.message }}</p>
        </div>
      </div>

      <!-- ═══════════════════════════════════════════
           视图 3：表格
           ═══════════════════════════════════════════ -->
      <CTable v-else-if="viewMode === 'table'">
        <thead>
          <tr>
            <th class="text-left">级别</th>
            <th class="text-left">标题</th>
            <th class="text-left">内容</th>
            <th class="text-left">时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="alert in filteredAlerts" :key="alert.id">
            <td>
              <span class="inline-flex items-center gap-1.5">
                <AlertLevelIcon :level="alert.level" simple :size="12" />
                <span class="text-xs" :class="levelClass(alert.level)">{{ levelLabel(alert.level) }}</span>
              </span>
            </td>
            <td class="text-sm text-ls-text">{{ alert.title }}</td>
            <td class="text-xs text-ls-dim max-w-xs truncate">{{ alert.message }}</td>
            <td class="text-xs text-ls-muted">{{ alert.timestamp }}</td>
          </tr>
          <tr v-if="filteredAlerts.length === 0">
            <td colspan="4" class="py-8 text-center text-ls-muted">暂无告警记录</td>
          </tr>
        </tbody>
      </CTable>
      </PageState>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import StatCard from '@/components/StatCard.vue'
import CCard from '@/components/CCard.vue'
import CTable from '@/components/CTable.vue'
import AlertLevelIcon from '@/components/AlertLevelIcon.vue'
import { getAlerts } from '@/api'
import CSelect from '@/components/CSelect.vue'
import ViewToggle from '@/components/ViewToggle.vue'
import { useViewPreference } from '@/composables/useViewPreference'

const ALERT_TYPE_OPTIONS = [
  { label: '全部类型', value: 'all' },
  { label: '配额耗尽', value: 'quota_exhausted' },
  { label: '请求失败', value: 'api_error' },
  { label: '供应商禁用', value: 'account_disabled' },
]

// ── 视图切换（持久化到 localStorage） ──
const viewMode = useViewPreference('alerts_view_mode', 'row')

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

// ── 顶部统计：全部由真实告警数据派生，不再硬编码 ──
const todayKey = () => new Date().toISOString().slice(0, 10) // YYYY-MM-DD
const isToday = (ts) => typeof ts === 'string' && ts.slice(0, 10) === todayKey()
const isSevere = (a) => a.level === 'error' || a.level === 'critical'

const stats = computed(() => {
  const list = alerts.value
  const today = list.filter(isToday).length
  const week = list.length

  // 近 7 日按类型细分
  const quota = list.filter(a => a.type === 'quota_exhausted').length
  const apiErr = list.filter(a => a.type === 'api_error').length
  const weekSub = week
    ? `配额耗尽 ${quota} · 请求失败 ${apiErr}`
    : '暂无告警'

  // 最近一条严重告警
  const severe = [...list].reverse().find(isSevere)
  const severeValue = severe ? '!' : '—'
  const severeSub = severe ? (severe.title || '存在严重告警') : '系统运行正常'
  const severeSubClass = severe ? 'text-red-400' : 'text-green-400'

  return {
    today,
    todaySub: today ? `今日 ${today} 条` : '今日无告警',
    week,
    weekSub,
    severeValue,
    severeSub,
    severeSubClass,
  }
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
