<script setup>
/**
 * QpsTrendChart — QPS 趋势面积图（手写 SVG，无图表库依赖）。
 * 精确对齐 demo：viewBox 700×200，5 条网格线，y 轴 niceMax 四分位刻度，
 * cyan 面积渐变 + 折线，绿色成功率线（隐藏标度贴顶，复刻 demo 观感），
 * 末端双圆点标记当前值。
 */
import { computed, ref, onMounted, onBeforeUnmount } from 'vue'
import { niceMax, smoothLinePath } from '@/utils/chart'

const props = defineProps({
  series: { type: Array, default: () => [] },
  windowSeconds: { type: Number, default: 300 },
})

// 用 ResizeObserver 监听容器宽度变化，驱动 SVG 重新拉伸
const containerRef = ref(null)
const resizeTick = ref(0)
let observer = null

onMounted(() => {
  if (containerRef.value) {
    observer = new ResizeObserver(() => { resizeTick.value++ })
    observer.observe(containerRef.value)
  }
})
onBeforeUnmount(() => {
  if (observer) { observer.disconnect(); observer = null }
})

// 绘图区：x ∈ [40, 690]，y ∈ [20, 160]
const X0 = 40, X1 = 690, Y0 = 20, Y1 = 160

const n = computed(() => props.series.length)
const xAt = (i) => (n.value > 1 ? X0 + (i * (X1 - X0)) / (n.value - 1) : X0)

const maxQps = computed(() => niceMax(Math.max(0, ...props.series.map(s => s.total || 0))))
const yQps = (v) => Y1 - (v / maxQps.value) * (Y1 - Y0)

const qpsPts = computed(() =>
  props.series.map((s, i) => [xAt(i), yQps(s.total || 0)])
)
const qpsLineD = computed(() => smoothLinePath(qpsPts.value))

const areaD = computed(() => {
  if (!n.value) return ''
  return `${qpsLineD.value} L${X1},${Y1} L${X0},${Y1} Z`
})

const lastPoint = computed(() => {
  if (!n.value) return null
  const last = props.series[n.value - 1]
  return { x: xAt(n.value - 1), y: yQps(last.total || 0) }
})

// y 轴刻度：满量程四分位（demo: 30 / 22.5 / 15 / 7.5 / 0）
const yLabels = computed(() => {
  const max = maxQps.value
  return [max, max * 0.75, max * 0.5, max * 0.25, 0].map((v, i) => ({
    y: Y0 + (i * (Y1 - Y0)) / 4 + 4,
    text: String(Math.round(v * 10) / 10),
  }))
})

// x 轴刻度：6 个等分点，从 series 取实际时间戳显示
const xTicks = computed(() => {
  const w = props.windowSeconds
  const series = props.series
  const n = series.length
  const label = (idx) => {
    if (idx >= n || idx < 0) return ''
    // 最后一点始终显示"现在"
    if (idx === n - 1) return '现在'
    const t = series[idx]?.t
    if (!t) return ''
    const d = new Date(t.replace(' ', 'T'))
    if (isNaN(d.getTime())) return ''
    if (w <= 86400) {
      // 1 天窗：显示时:分
      const h = String(d.getHours()).padStart(2, '0')
      const m = String(d.getMinutes()).padStart(2, '0')
      return `${h}:${m}`
    }
    // 7 天 / 30 天窗：显示月/日
    const mo = String(d.getMonth() + 1).padStart(2, '0')
    const da = String(d.getDate()).padStart(2, '0')
    return `${mo}/${da}`
  }
  return [0, 0.2, 0.4, 0.6, 0.8, 1].map(f => ({
    x: X0 + f * (X1 - X0),
    label: label(Math.round(f * (n - 1))),
  }))
})
</script>

<template>
  <div ref="containerRef" style="width:100%">
    <svg class="w-full" viewBox="0 0 700 200" preserveAspectRatio="none" style="display:block">
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

    <!-- QPS 面积 + 平滑曲线 -->
    <path fill="url(#qpsGrad)" :d="areaD" />
    <path fill="none" stroke="var(--ls-accent)" stroke-width="2"
      stroke-linejoin="round" stroke-linecap="round" :d="qpsLineD" />
    <!-- 当前点 -->
    <template v-if="lastPoint">
      <circle :cx="lastPoint.x" :cy="lastPoint.y" r="4" fill="var(--ls-accent)" />
      <circle :cx="lastPoint.x" :cy="lastPoint.y" r="2" fill="var(--text)" />
    </template>
  </svg>
  </div>
</template>
