<template>
  <div>
    <PageHeader title="Dashboard // Monitor" subtitle="// 实时查看 API 调用状态、模型健康度和资源消耗">
      <template #action>
        <span class="inline-flex items-center gap-1.5 text-xs text-ls-dim">
          <span class="pulse-live h-2 w-2 rounded-full bg-ls-accent"></span>
          实时
        </span>
        <SegmentedControl v-model="windowSeconds" :options="WINDOW_OPTIONS" variant="neon" />
      </template>
    </PageHeader>

    <PageState :loading="loading" :error="error" loading-text="加载中..." error-prefix="错误: ">
      <div class="px-6 md:px-8 py-6 space-y-6">

        <!-- ── KPI 卡片 ── -->
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
          <!-- 总请求 -->
          <StatCard label="总请求" :value="fmtInt(kpi.total)"
            :delta="totalDelta.text" :delta-class="totalDelta.cls" icon-bg-class="bg-ls-accent/10">
            <template #icon>
              <svg class="w-3.5 h-3.5 text-ls-accent" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
              </svg>
            </template>
            <template #footer>
              <KpiSparkline :values="series.map(s => s.total)" stroke="#00ffff" />
            </template>
          </StatCard>

          <!-- 成功率 -->
          <StatCard label="成功率" :value="kpi.success_rate != null ? kpi.success_rate.toFixed(1) + '%' : '—'"
            :delta="rateDelta.text" :delta-class="rateDelta.cls" icon-bg-class="bg-green-500/10">
            <template #icon>
              <svg class="w-3.5 h-3.5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </template>
            <template #footer>
              <ProgressBar :pct="kpi.success_rate || 0" width="w-full" height="h-1.5"
                bar-class="bg-gradient-to-r from-green-400 to-green-500" />
            </template>
          </StatCard>

          <!-- QPS -->
          <StatCard label="QPS" :value="kpi.qps != null ? kpi.qps.toFixed(1) : '0.0'" unit="req/s"
            :delta="qpsDelta.text" :delta-class="qpsDelta.cls" icon-bg-class="bg-purple-500/10">
            <template #icon>
              <svg class="w-3.5 h-3.5 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z"/>
              </svg>
            </template>
            <template #footer>
              <KpiSparkline :values="series.map(s => s.qps)" stroke="#a855f7" />
            </template>
          </StatCard>

          <!-- 平均响应 -->
          <StatCard label="平均响应" :value="kpi.avg_latency_ms != null ? String(kpi.avg_latency_ms) : '—'" unit="ms"
            :delta="latencyDelta.text" :delta-class="latencyDelta.cls" icon-bg-class="bg-blue-500/10">
            <template #icon>
              <svg class="w-3.5 h-3.5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
              </svg>
            </template>
            <template #footer>
              <KpiSparkline :values="series.map(s => s.avg_latency_ms)" stroke="#3b82f6" />
            </template>
          </StatCard>
        </div>

        <!-- ── 图表行：QPS 趋势 + 请求结果分布 ── -->
        <div class="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div class="lg:col-span-2 bg-ls-card rounded-lg border border-ls-border p-5 neon-glow">
            <div class="flex items-center justify-between mb-4">
              <div>
                <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">QPS 趋势 // Trend</h3>
                <p class="text-xs text-ls-muted mt-0.5">// 最近 {{ windowLabel }}每秒请求数变化</p>
              </div>
              <div class="flex items-center gap-4 text-xs">
                <span class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded bg-ls-accent"></span>QPS
                </span>
                <span class="flex items-center gap-1.5">
                  <span class="w-2 h-2 rounded bg-[#22c55e]"></span>成功率
                </span>
              </div>
            </div>
            <QpsTrendChart :series="series" :window-seconds="windowSeconds" />
          </div>

          <StatusDonut :success="kpi.success || 0" :failed="kpi.failed || 0" :status-codes="statusCodes" />
        </div>

        <!-- ── 模型状态 ── -->
        <ModelStatusTable :quotas="quotas" :model-stats="models" />

        <!-- ── 限流状态 + 最近告警 ── -->
        <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <RateLimitCard :quotas="quotas" />
          <RecentAlerts :alerts="recentAlerts" />
        </div>

      </div>
    </PageState>

    <!-- Footer -->
    <div class="border-t border-ls-border mt-12">
      <div class="px-6 md:px-8 py-6 flex items-center justify-between text-sm text-ls-muted">
        <span>&copy; 2026 AI Provider Platform</span>
        <div class="flex items-center gap-4">
          <router-link to="/guide" class="hover:text-ls-accent transition-colors">文档</router-link>
          <router-link to="/keys" class="hover:text-ls-accent transition-colors">API</router-link>
          <router-link to="/alerts" class="hover:text-ls-accent transition-colors">状态</router-link>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import PageState from '@/components/PageState.vue'
import StatCard from '@/components/StatCard.vue'
import SegmentedControl from '@/components/SegmentedControl.vue'
import ProgressBar from '@/components/ProgressBar.vue'
import KpiSparkline from '@/components/dashboard/KpiSparkline.vue'
import QpsTrendChart from '@/components/dashboard/QpsTrendChart.vue'
import StatusDonut from '@/components/dashboard/StatusDonut.vue'
import ModelStatusTable from '@/components/dashboard/ModelStatusTable.vue'
import RateLimitCard from '@/components/dashboard/RateLimitCard.vue'
import RecentAlerts from '@/components/dashboard/RecentAlerts.vue'
import { getWindowStats, getModelQuotas, getAlerts } from '@/api'

// ── 时间窗 ──
const WINDOW_OPTIONS = [
  { label: '5 分钟', value: 300 },
  { label: '1 小时', value: 3600 },
  { label: '24 小时', value: 86400 },
]
const windowSeconds = ref(300)
const windowLabel = computed(() => {
  const opt = WINDOW_OPTIONS.find(o => o.value === windowSeconds.value)
  return opt ? opt.label : `${windowSeconds.value}s`
})

const loading = ref(true)
const error = ref(null)
const stats = ref(null)    // /stats/window payload
const quotas = ref([])     // /model-quota
const alertsRaw = ref([])  // /alerts(7)，客户端过滤最近 1 小时

const kpi = computed(() => stats.value?.kpi || {})
const series = computed(() => stats.value?.series || [])
const models = computed(() => stats.value?.models || [])
const statusCodes = computed(() => stats.value?.status_codes || {})

// 最近 1 小时告警，倒序，cap 5
const recentAlerts = computed(() => {
  const cutoff = Date.now() - 3600000
  return (alertsRaw.value || [])
    .filter(a => {
      const t = new Date(String(a.timestamp || '').replace(' ', 'T') + 'Z').getTime()
      return !isNaN(t) && t >= cutoff
    })
    .slice(0, 5)
})

// ── delta 趋势芯片：null → 灰 '—'；invert 用于延迟（下降为绿）；
//    neutralBelow 之内视为平稳（黄），对应 demo 的 ±2.1% 芯片 ──
function deltaChip(pct, { invert = false, neutralBelow = 0 } = {}) {
  if (pct === null || pct === undefined) {
    return { text: '—', cls: 'bg-ls-elevated text-ls-muted' }
  }
  const text = `${pct > 0 ? '+' : ''}${pct}%`
  if (Math.abs(pct) <= neutralBelow) return { text, cls: 'bg-yellow-500/10 text-yellow-400' }
  const good = invert ? pct < 0 : pct > 0
  return {
    text,
    cls: good ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400',
  }
}

const totalDelta = computed(() => deltaChip(kpi.value.delta?.total_pct))
const rateDelta = computed(() => deltaChip(kpi.value.delta?.success_rate_pp))
// QPS 与总请求等窗长，delta 数学等价，复用 total_pct
const qpsDelta = computed(() => deltaChip(kpi.value.delta?.total_pct, { neutralBelow: 3 }))
const latencyDelta = computed(() => deltaChip(kpi.value.delta?.avg_latency_pct, { invert: true }))

const fmtInt = (n) => (n || 0).toLocaleString()

// ── 数据加载：首载走 PageState 三态，之后静默刷新不闪 loading ──
async function loadAll() {
  if (!stats.value) {
    loading.value = true
    error.value = null
  }
  const [s, q, a] = await Promise.allSettled([
    getWindowStats(windowSeconds.value),
    getModelQuotas(),
    getAlerts(7),
  ])
  if (s.status === 'fulfilled') {
    stats.value = s.value.data
  } else if (!stats.value) {
    error.value = s.reason?.message || '加载统计数据失败'
  }
  if (q.status === 'fulfilled') quotas.value = q.value.data || []
  if (a.status === 'fulfilled') alertsRaw.value = a.value.data || []
  loading.value = false
}

watch(windowSeconds, loadAll)

// 30s 自动刷新（同 Logs.vue 的定时模式）
let refreshTimer = null
onMounted(() => {
  loadAll()
  refreshTimer = setInterval(loadAll, 30000)
})
onUnmounted(() => { if (refreshTimer) clearInterval(refreshTimer) })
</script>
