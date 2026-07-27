<script setup>
/**
 * QpsTrendChart — QPS 趋势面积图（手写 SVG，无图表库依赖）。
 * 精确对齐 demo：viewBox 700×200，5 条网格线，y 轴 niceMax 四分位刻度，
 * cyan 面积渐变 + 折线，末端双圆点标记当前值。
 *
 * 交互：
 *  - y 轴刻度恒为整数（上限向上取到 4 的倍数，保证 1/4 分段均为整数）。
 *  - 鼠标在绘图区移动时，按最近数据点显示 Chart.js 风格 tooltip（时间 + 请求数）。
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

// y 轴上限：先取 nice 数字，再向上取到 4 的倍数，使四分位刻度恒为整数。
const topVal = computed(() => niceMax(Math.max(0, ...props.series.map(s => s.total || 0))))
const maxQps = computed(() => Math.max(1, Math.ceil(topVal.value / 4) * 4))
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

// y 轴刻度：满量程四分位（整数，如 32 / 24 / 16 / 8 / 0）
const yLabels = computed(() => {
  const max = maxQps.value
  return [max, max * 0.75, max * 0.5, max * 0.25, 0].map((v, i) => ({
    y: Y0 + (i * (Y1 - Y0)) / 4 + 4,
    text: String(Math.round(v)),
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

// ── tooltip：鼠标移动时按最近数据点显示 ──
const tip = ref({ show: false, x: 0, y: 0, title: '', value: 0 })
const hoverIdx = ref(null)

const hoverPt = computed(() => {
  if (hoverIdx.value == null || !n.value) return null
  const s = props.series[hoverIdx.value]
  if (!s) return null
  return { x: xAt(hoverIdx.value), y: yQps(s.total || 0) }
})

function fmtTipTime(s) {
  const t = s?.t
  if (!t) return ''
  const d = new Date(String(t).replace(' ', 'T'))
  if (isNaN(d.getTime())) return ''
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const da = String(d.getDate()).padStart(2, '0')
  if (props.windowSeconds <= 86400) {
    const h = String(d.getHours()).padStart(2, '0')
    const m = String(d.getMinutes()).padStart(2, '0')
    return `${mo}-${da} ${h}:${m}`
  }
  return `${mo}-${da}`
}

function onMove(e) {
  const el = containerRef.value
  if (!el || !n.value) return
  const rect = el.getBoundingClientRect()
  const vbX = ((e.clientX - rect.left) / rect.width) * 700
  let f = (vbX - X0) / (X1 - X0)
  f = Math.max(0, Math.min(1, f))
  const i = Math.round(f * (n.value - 1))
  hoverIdx.value = i
  const s = props.series[i]
  if (!s) return
  const pxX = (xAt(i) / 700) * rect.width
  const pyY = (yQps(s.total || 0) / 200) * rect.height
  tip.value = {
    show: true,
    x: pxX,
    y: pyY,
    title: fmtTipTime(s),
    value: s.total || 0,
  }
}

function onLeave() {
  tip.value.show = false
  hoverIdx.value = null
}
</script>

<template>
  <div ref="containerRef" style="width:100%;position:relative">
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
    <!-- hover 高亮圆点 -->
    <circle v-if="hoverPt" :cx="hoverPt.x" :cy="hoverPt.y" r="4.5"
      fill="var(--ls-accent)" stroke="var(--text)" stroke-width="1.5" />

    <!-- 透明覆盖层：捕获鼠标移动，按最近数据点触发 tooltip -->
    <rect :x="X0" :y="Y0" :width="X1 - X0" :height="Y1 - Y0"
      fill="transparent" style="cursor:crosshair"
      @mousemove="onMove" @mouseleave="onLeave" />
  </svg>

  <!-- Chart.js 风格 tooltip：黑底 0.8 / 圆角 6 / 白字 / 彩色小方块，位置缓动 + 淡入淡出 -->
  <div class="cjs-tip" :class="{ 'is-show': tip.show }"
    :style="{ left: tip.x + 'px', top: tip.y + 'px' }">
    <div class="cjs-tip-box">
      <div class="cjs-tip-title">{{ tip.title || '—' }}</div>
      <div class="cjs-tip-row">
        <span class="cjs-tip-swatch" style="background: var(--ls-accent)"></span>
        请求数: {{ tip.value }}
      </div>
    </div>
    <div class="cjs-tip-caret"></div>
  </div>
  </div>
</template>

<style scoped>
/* ═══ 原型（Chart.js 默认）tooltip 复刻：位置缓动 + 淡入淡出 ═══ */
.cjs-tip {
  position: absolute;
  z-index: 50;
  pointer-events: none;
  transform: translate(-50%, -100%);
  margin-top: -6px;
  display: flex;
  flex-direction: column;
  align-items: center;
  opacity: 0;
  transition: left 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
              top 0.2s cubic-bezier(0.25, 0.1, 0.25, 1),
              opacity 0.15s ease;
}
.cjs-tip.is-show {
  opacity: 1;
}
.cjs-tip-box {
  background: rgba(0, 0, 0, 0.8);
  border-radius: 6px;
  padding: 6px 10px;
  color: #fff;
  white-space: nowrap;
}
.cjs-tip-title {
  font-size: 12px;
  font-weight: 700;
  margin-bottom: 4px;
}
.cjs-tip-row {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  line-height: 1.5;
  font-variant-numeric: tabular-nums;
}
.cjs-tip-swatch {
  width: 12px;
  height: 12px;
  display: inline-block;
  flex-shrink: 0;
  border-radius: 2px;
}
.cjs-tip-caret {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid rgba(0, 0, 0, 0.8);
}
</style>
