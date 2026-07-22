<script setup>
/**
 * QpsTrendChart — QPS 趋势面积图（手写 SVG，无图表库依赖）。
 * 精确对齐 demo：viewBox 700×200，5 条网格线，y 轴 niceMax 四分位刻度，
 * cyan 面积渐变 + 折线，绿色成功率线（隐藏标度贴顶，复刻 demo 观感），
 * 末端双圆点标记当前值。
 */
import { computed } from 'vue'
import { niceMax } from '@/utils/chart'

const props = defineProps({
  series: { type: Array, default: () => [] },   // [{ t, qps, success_rate, ... }]
  windowSeconds: { type: Number, default: 300 },
})

// 绘图区：x ∈ [40, 690]，y ∈ [20, 160]
const X0 = 40, X1 = 690, Y0 = 20, Y1 = 160

const n = computed(() => props.series.length)
const xAt = (i) => (n.value > 1 ? X0 + (i * (X1 - X0)) / (n.value - 1) : X0)

const maxQps = computed(() => niceMax(Math.max(0, ...props.series.map(s => s.qps || 0))))
const yQps = (v) => Y1 - (v / maxQps.value) * (Y1 - Y0)

// 成功率线：隐藏标度 [min(95, ⌊最低值⌋), 100]，让曲线贴在图顶部（demo 形态）
const rateMin = computed(() => {
  const rates = props.series.map(s => s.success_rate).filter(r => r !== null && r !== undefined)
  return rates.length ? Math.min(95, Math.floor(Math.min(...rates))) : 95
})
const yRate = (r) => {
  if (r === null || r === undefined) return null
  const span = Math.max(1, 100 - rateMin.value)
  return Y1 - ((r - rateMin.value) / span) * (Y1 - Y0)
}

const qpsPoints = computed(() =>
  props.series.map((s, i) => `${xAt(i).toFixed(1)},${yQps(s.qps || 0).toFixed(1)}`).join(' ')
)

const areaD = computed(() => {
  if (!n.value) return ''
  const line = props.series
    .map((s, i) => `${i === 0 ? 'M' : 'L'}${xAt(i).toFixed(1)},${yQps(s.qps || 0).toFixed(1)}`)
    .join(' ')
  return `${line} L${X1},${Y1} L${X0},${Y1} Z`
})

const ratePoints = computed(() =>
  props.series
    .map((s, i) => {
      const y = yRate(s.success_rate)
      return y === null ? null : `${xAt(i).toFixed(1)},${y.toFixed(1)}`
    })
    .filter(Boolean)
    .join(' ')
)

const lastPoint = computed(() => {
  if (!n.value) return null
  const last = props.series[n.value - 1]
  return { x: xAt(n.value - 1), y: yQps(last.qps || 0) }
})

// y 轴刻度：满量程四分位（demo: 30 / 22.5 / 15 / 7.5 / 0）
const yLabels = computed(() => {
  const max = maxQps.value
  return [max, max * 0.75, max * 0.5, max * 0.25, 0].map((v, i) => ({
    y: Y0 + (i * (Y1 - Y0)) / 4 + 4,
    text: String(Math.round(v * 10) / 10),
  }))
})

// x 轴刻度：6 个等分点。5 分钟窗 → '-5:00'…'现在'；1 小时 → '-60m'；24 小时 → '-24h'
const xTicks = computed(() => {
  const w = props.windowSeconds
  const label = (agoSec) => {
    if (agoSec <= 0) return '现在'
    if (w <= 600) {
      const m = Math.floor(agoSec / 60)
      const s = Math.round(agoSec % 60)
      return `-${m}:${String(s).padStart(2, '0')}`
    }
    if (w < 86400) return `-${Math.round(agoSec / 60)}m`
    return `-${Math.round(agoSec / 3600)}h`
  }
  return [0, 0.2, 0.4, 0.6, 0.8, 1].map(f => ({
    x: X0 + f * (X1 - X0),
    label: label(w - f * w),
  }))
})
</script>

<template>
  <svg class="w-full" viewBox="0 0 700 200" preserveAspectRatio="none">
    <!-- 网格 -->
    <g class="chart-grid">
      <line v-for="i in 5" :key="i" :x1="X0" :x2="X1" :y1="Y0 + (i - 1) * 35" :y2="Y0 + (i - 1) * 35" />
    </g>
    <!-- y 轴刻度 -->
    <g class="chart-label">
      <text v-for="lb in yLabels" :key="lb.y" :x="35" :y="lb.y" text-anchor="end">{{ lb.text }}</text>
    </g>
    <!-- x 轴刻度 -->
    <g class="chart-label">
      <text v-for="tk in xTicks" :key="tk.x" :x="tk.x" y="185" text-anchor="middle">{{ tk.label }}</text>
    </g>

    <defs>
      <linearGradient id="qpsGrad" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="var(--ls-accent)" stop-opacity="0.2" />
        <stop offset="100%" stop-color="var(--ls-accent)" stop-opacity="0" />
      </linearGradient>
    </defs>

    <!-- QPS 面积 + 折线 -->
    <path fill="url(#qpsGrad)" :d="areaD" />
    <polyline fill="none" stroke="var(--ls-accent)" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round" :points="qpsPoints" />
    <!-- 成功率线 -->
    <polyline v-if="ratePoints" fill="none" stroke="#22c55e" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round" opacity="0.8" :points="ratePoints" />
    <!-- 当前点 -->
    <template v-if="lastPoint">
      <circle :cx="lastPoint.x" :cy="lastPoint.y" r="4" fill="var(--ls-accent)" />
      <circle :cx="lastPoint.x" :cy="lastPoint.y" r="2" fill="var(--text)" />
    </template>
  </svg>
</template>
