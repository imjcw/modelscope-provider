<template>
  <div>
    <PageHeader :title="pageTitle" :subtitle="today">
      <template #action>
        <span class="inline-flex items-center rounded-md px-2 py-0.5 bg-green-500/10 text-green-400 text-xs">● 运行正常</span>
      </template>
    </PageHeader>

    <div class="p-6">
      <div v-if="loading" class="flex items-center justify-center h-64">
        <div class="text-gray-500">加载中...</div>
      </div>
      <div v-else-if="error" class="text-red-400 text-sm p-4">错误: {{ error }}</div>
      <div v-else>

      <!-- ── 概览卡片 ── -->
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5 mb-6">
        <div v-for="card in statCards" :key="card.label" class="bg-ls-card rounded-lg border border-ls-border p-5">
          <p class="text-xs text-gray-500 mb-1">{{ card.label }}</p>
          <p class="text-2xl font-semibold tracking-tight text-white">{{ card.value }}</p>
          <p :class="['text-xs mt-1', card.trendColor || 'text-gray-500']">{{ card.sub }}</p>
        </div>
      </div>

      <!-- ── 使用热力图 ── -->

      <!-- ── Token 趋势折线图 ── -->
      <div class="bg-ls-card rounded-lg border border-ls-border p-5 mb-6">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-semibold tracking-tight text-sm">Token 趋势</h2>
          <div class="flex items-center gap-4">
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-2.5 h-0.5 rounded bg-blue-400"></span>Input
            </span>
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-2.5 h-0.5 rounded bg-emerald-400"></span>Output
            </span>
            <span class="flex items-center gap-1.5 text-xs text-gray-400">
              <span class="w-2.5 h-0.5 rounded bg-amber-400"></span>Cached
            </span>
            <div class="w-36">
              <CSelect v-model="trendDays" :options="TREND_OPTIONS" size="sm" placeholder="天数" />
            </div>
          </div>
        </div>
        <div v-if="trendLines.length" class="relative" style="height: 180px;">
          <!-- Grid lines -->
          <div class="absolute inset-0 flex flex-col justify-between pointer-events-none">
            <div v-for="i in 5" :key="i" class="border-t border-ls-border/50"></div>
          </div>
          <!-- SVG line chart -->
          <svg class="absolute inset-0 w-full h-full" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid meet">
            <polyline :points="trendLines.input" fill="none" stroke="#60a5fa" stroke-width="0.8" :vector-effect="'non-scaling-stroke'" />
            <polyline :points="trendLines.output" fill="none" stroke="#34d399" stroke-width="0.8" :vector-effect="'non-scaling-stroke'" />
            <polyline :points="trendLines.cached" fill="none" stroke="#fbbf24" stroke-width="0.8" :vector-effect="'non-scaling-stroke'" />
          </svg>
          <!-- X-axis labels -->
          <div class="absolute bottom-0 left-0 right-0 flex justify-between text-[9px] text-gray-600 pt-1">
            <span v-for="label in trendLabels" :key="label">{{ label }}</span>
          </div>
        </div>
        <div v-else class="flex items-center justify-center h-44 text-gray-600 text-sm">暂无趋势数据</div>
      </div>

      <!-- 模型用量分布 -->
      <div class="mb-6">

        <!-- 左: 模型用量环形图 + Top 5 -->
        <div class="bg-ls-card rounded-lg border border-ls-border p-5">
          <h2 class="font-semibold tracking-tight text-sm mb-5">模型用量分布</h2>
          <div class="flex items-center gap-6">
            <div class="flex-shrink-0">
              <svg width="160" height="160" viewBox="0 0 160 160">
                <circle cx="80" cy="80" r="60" fill="none" stroke="#0e0e10" stroke-width="20"/>
                <circle v-for="seg in donutSegs" :key="seg.label" cx="80" cy="80" r="60" fill="none"
                  :stroke="seg.color" :stroke-width="20"
                  :stroke-dasharray="seg.dash" :stroke-dashoffset="seg.offset"
                  transform="rotate(-90 80 80)"/>
                <text x="80" y="76" text-anchor="middle" style="font-size:16px;font-weight:700" fill="white">{{ donutTotalLabel }}</text>
                <text x="80" y="92" text-anchor="middle" style="font-size:10px" fill="#6b7280">tokens</text>
              </svg>
            </div>
            <div class="flex-1 space-y-2.5 min-w-0">
              <div v-for="seg in donutSegs" :key="seg.label" class="flex items-center justify-between">
                <div class="flex items-center gap-2 min-w-0">
                  <span class="w-2.5 h-2.5 rounded flex-shrink-0" :style="{ backgroundColor: seg.color }"></span>
                  <span class="text-sm text-white truncate">{{ seg.label }}</span>
                </div>
                <div class="flex items-center gap-3 flex-shrink-0">
                  <span class="text-xs text-gray-400">{{ seg.tokens }}</span>
                  <span class="text-sm font-mono text-white w-10 text-right">{{ seg.pct }}%</span>
                </div>
              </div>
              <hr class="border-ls-border">
              <div class="flex items-center justify-between">
                <span class="text-sm text-gray-400">总计</span>
                <span class="text-base font-bold text-white font-mono">{{ donutTotalLabel }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ── 供应商列表 ── -->
      <div class="bg-ls-card rounded-lg border border-ls-border">
        <div class="px-5 py-3.5 border-b border-ls-border flex items-center justify-between">
          <h2 class="font-semibold tracking-tight text-sm">供应商列表</h2>
          <router-link to="/suppliers" class="text-xs text-gray-500 hover:text-white">查看全部 →</router-link>
        </div>
        <table class="w-full text-sm">
          <thead>
            <tr class="text-gray-500 border-b border-ls-border text-xs">
              <th class="text-left px-5 py-2.5 font-medium">供应商</th>
              <th class="text-left px-5 py-2.5 font-medium">状态</th>
              <th class="text-left px-5 py-2.5 font-medium">配额</th>
              <th class="text-left px-5 py-2.5 font-medium">今日</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="acc in suppliers" :key="acc.id" class="border-b border-ls-border/50">
              <td class="px-5 py-3 font-medium text-white">{{ acc.name }}</td>
              <td class="px-5 py-3">
                <span class="inline-flex items-center rounded-md px-2 py-0.5"
                  :class="acc.status === 'active' ? 'bg-green-500/10 text-green-400' : 'bg-ls-elevated text-gray-400'">
                  <span class="w-1.5 h-1.5 rounded-full mr-1.5"
                    :class="acc.status === 'active' ? 'bg-green-400' : 'bg-gray-500'"></span>
                  {{ acc.status === 'active' ? '活跃' : '已禁用' }}
                </span>
              </td>
              <td class="px-5 py-3 text-xs text-gray-400">{{ acc.quota }}</td>
              <td class="px-5 py-3 text-xs text-gray-500">{{ acc.today }}</td>
            </tr>
            <tr v-if="suppliers.length === 0">
              <td colspan="4" class="px-5 py-8 text-center text-gray-500">尚未配置供应商，前往供应商管理页面添加。</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import PageHeader from '@/components/PageHeader.vue'
import CSelect from '@/components/CSelect.vue'
import { getSuppliers, getLogs, getStats, getModelQuotas } from '@/api'

const pageTitle = '仪表盘'
const today = computed(() => {
  return new Date().toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' })
})

const TREND_OPTIONS = [
  { label: '最近 7 天', value: '7' },
  { label: '最近 30 天', value: '30' },
  { label: '最近 90 天', value: '90' },
]

const loading = ref(true)
const error = ref(null)

// Stat cards
const statCards = ref([
  { label: '今日请求', value: '...', sub: '加载中...', trendColor: 'text-gray-500' },
  { label: '累计 Token', value: '...', sub: '全部时间', trendColor: 'text-gray-500' },
  { label: '缓存命中率', value: '...', sub: '加载中...', trendColor: 'text-gray-500' },
  { label: '平均延迟', value: '...', sub: '加载中...', trendColor: 'text-gray-500' },
])

const suppliers = ref([])
const modelQuotas = ref([])
const trendDays = ref('30')

// Group model quotas by supplier
const groupedModelQuotas = computed(() => {
  const groups = {}
  for (const mq of modelQuotas.value) {
    const name = mq.supplier_name || '未知供应商'
    if (!groups[name]) groups[name] = { supplier_name: name, models: [] }
    groups[name].models.push(mq)
  }
  return Object.values(groups)
})

// ── Trend line chart ──
const trendLines = ref({ input: '', output: '', cached: '' })
const trendLabels = ref([])

// ── Donut chart ──
const MODEL_COLORS = ['#89b4fa', '#a6e3a1', '#f9e2af', '#f38ba8', '#cba6f7']
const donutSegs = ref([])
const donutTotalLabel = ref('0')

// ── Supplier ranking ──
const supplierRanking = ref([])
const quotaUsed = ref(0)
const quotaTotal = ref(0)
const quotaUsedPct = computed(() => quotaTotal.value ? Math.round(quotaUsed.value / quotaTotal.value * 100) : 0)

const formatNumber = (n) => {
  if (n >= 1e8) return (n / 1e8).toFixed(1) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + '万'
  return n.toLocaleString()
}

const buildPolylinePoints = (values, w, h) => {
  if (!values.length) return ''
  const max = Math.max(...values, 1)
  return values.map((v, i) => {
    const x = (i / Math.max(1, values.length - 1)) * w
    const y = h - (v / max) * (h - 4) - 2
    return `${x},${y}`
  }).join(' ')
}



const loadData = async () => {
  loading.value = true
  error.value = null
  try {
    const [suppliersRes, logsRes, statsRes, modelQuotasRes] = await Promise.allSettled([
      getSuppliers(),
      getLogs({ page: 0, page_size: 20 }),
      getStats(Number(trendDays.value)),
      getModelQuotas(),
    ])

    // Model quotas
    if (modelQuotasRes.status === 'fulfilled') {
      modelQuotas.value = modelQuotasRes.value.data || []
    }

    // Suppliers
    if (suppliersRes.status === 'fulfilled') {
      const sups = suppliersRes.value.data || []
      suppliers.value = sups.map(a => ({
        id: a.id,
        name: a.name || a.account_id,
        status: a.status,
        usage: a.quota_remaining != null && a.quota_limit && a.quota_limit > 0
          ? Math.round((a.quota_limit - a.quota_remaining) / a.quota_limit * 100)
          : 0,
        quota: a.quota_limit > 0 ? `${a.quota_remaining || 0} / ${a.quota_limit}` : '—',
        today: '—',
      }))
      quotaTotal.value = sups.reduce((s, a) => s + (a.quota_limit || 0), 0)
      quotaUsed.value = sups.reduce((s, a) => s + (a.quota_remaining != null ? a.quota_limit - a.quota_remaining : 0), 0)
      supplierRanking.value = sups.map(a => ({
        id: a.id,
        name: a.name || a.account_id,
        requests: a.today_req || 0,
      })).sort((a, b) => b.requests - a.requests)
    }

    // Logs
    if (logsRes.status === 'fulfilled') {
      const total = logsRes.value.data?.total || 0
      statCards.value[0].value = total.toLocaleString()
      statCards.value[0].sub = '今日'
    }

    // Stats
    if (statsRes.status === 'fulfilled') {
      const s = statsRes.value.data || {}

      // Total tokens
      const totalTok = s.total_tokens || 0
      statCards.value[1].value = formatNumber(totalTok)
      statCards.value[1].sub = '全部时间'

      // Cache hit rate
      const chr = s.cache_hit_rate ?? 0
      statCards.value[2].value = chr > 0 ? `${chr}%` : '—'
      statCards.value[2].sub = chr > 0 ? '缓存命中' : '无缓存数据'
      statCards.value[2].trendColor = chr > 0 ? 'text-emerald-400' : 'text-gray-500'

      // Avg latency
      const avgLat = s.avg_latency ?? s.avg_latency_ms ?? null
      statCards.value[3].value = avgLat != null ? `${avgLat}ms` : '—'
      statCards.value[3].sub = avgLat != null ? '平均值' : '无数据'

      // ── Token trend line chart ──
      const dailyTrend = s.daily_trend || {}
      const days = Object.keys(dailyTrend).sort()
      const recentDays = days.slice(-Number(trendDays.value))
      const inputVals = recentDays.map(d => dailyTrend[d]?.input || 0)
      const outputVals = recentDays.map(d => dailyTrend[d]?.output || 0)
      const cachedVals = recentDays.map(d => dailyTrend[d]?.cached || 0)

      trendLines.value = {
        input: buildPolylinePoints(inputVals, 100, 100),
        output: buildPolylinePoints(outputVals, 100, 100),
        cached: buildPolylinePoints(cachedVals, 100, 100),
      }
      trendLabels.value = recentDays.map(d => {
        const parts = d.split('-')
        return `${parts[1]}/${parts[2]}`
      })

      // ── Donut chart ──
      const usage = s.model_usage || {}
      const total = Object.values(usage).reduce((a, b) => a + b, 0)
      donutTotalLabel.value = formatNumber(total)
      let offset = 0
      const circumference = 2 * Math.PI * 60
      donutSegs.value = Object.entries(usage).map(([label, tokens], i) => {
        const pct = total ? Math.round(tokens / total * 100) : 0
        const dash = (pct / 100) * circumference
        const seg = {
          label,
          tokens: formatNumber(tokens) + ' tokens',
          pct,
          color: MODEL_COLORS[i % MODEL_COLORS.length],
          dash: dash.toFixed(1),
          offset: (-offset).toFixed(1),
        }
        offset += dash
        return seg
      })

      // ── Supplier daily ranking ──
      const supplierDaily = s.supplier_daily || {}
      const todayStr = new Date().toISOString().slice(0, 10)
      supplierRanking.value = supplierRanking.value.map(acc => {
        const reqCount = supplierDaily[acc.id]?.[todayStr] || 0
        // Also update the corresponding supplier's today count
        const supIdx = suppliers.value.findIndex(s => s.id === acc.id)
        if (supIdx >= 0) {
          suppliers.value[supIdx].today = reqCount > 0 ? `${reqCount} 次` : '—'
        }
        return {
          ...acc,
          requests: reqCount,
        }
      }).sort((a, b) => b.requests - a.requests)

    }
  } catch (e) {
    error.value = e.message || '加载数据失败'
  }
  loading.value = false
}

// Reload on trendDays change
let reloadTimer = null
const watchTrendDays = () => {
  clearTimeout(reloadTimer)
  reloadTimer = setTimeout(loadData, 300)
}

onMounted(() => loadData())

watch(trendDays, watchTrendDays)
</script>
