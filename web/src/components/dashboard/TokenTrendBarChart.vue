<template>
  <!-- Token 趋势卡片：背景/字体对齐"请求趋势"卡片，柱体保留 Japanese Fresh 配色 -->
  <div class="bg-ls-card rounded-lg border border-ls-border p-5 neon-glow">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h3 class="text-sm uppercase tracking-[0.15em] text-ls-text">Token 趋势 // Token Trend</h3>
        <p class="text-xs text-ls-muted mt-0.5">// 最近 {{ windowLabel }}输入 / 命中 / 输出 Token 分布</p>
      </div>
      <div class="flex items-center gap-4 text-xs">
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded" :style="{ background: COLORS.input }"></span>输入
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded" :style="{ background: COLORS.cached }"></span>命中
        </span>
        <span class="flex items-center gap-1.5">
          <span class="w-2 h-2 rounded" :style="{ background: COLORS.output }"></span>输出
        </span>
      </div>
    </div>

    <div class="chart-wrap" ref="containerRef">
      <svg class="chart-svg" :viewBox="`0 0 ${W} ${H}`">
        <!-- y 轴网格线 -->
        <g class="chart-grid">
          <line v-for="t in yTicks" :key="'g' + t.v"
            :x1="X0" :x2="X1" :y1="t.y" :y2="t.y" />
        </g>

        <!-- x 轴 border -->
        <line :x1="X0" :x2="X1" :y1="Y1" :y2="Y1" stroke="var(--ls-border)" stroke-width="1" />

        <!-- y 轴刻度文字 -->
        <g class="chart-label">
          <text v-for="t in yTicks" :key="'yl' + t.v"
            :x="X0 - 8" :y="t.y + 3" text-anchor="end">{{ fmtK(t.v) }}</text>
        </g>

        <!-- ═══ 堆叠柱：底段圆底角 4 / 中段方角 / 顶段圆顶角 4，barThickness 15 ═══ -->
        <g>
          <template v-for="b in bars" :key="'b' + b.i">
            <path v-if="b.inputH > 0" :d="b.inputPath" :style="{ fill: COLORS.input }" />
            <path v-if="b.cacheH > 0" :d="b.cachePath" :style="{ fill: COLORS.cached }" />
            <path v-if="b.outputH > 0" :d="b.outputPath" :style="{ fill: COLORS.output }" />
          </template>
        </g>

        <!-- 命中区（透明，触发 tooltip） -->
        <g>
          <rect v-for="b in bars" :key="'h' + b.i"
            :x="b.slotX" :y="Y0" :width="b.slotW" :height="Y1 - Y0"
            fill="transparent" style="cursor:default"
            @mouseenter="onBarEnter($event, b)" @mouseleave="onBarLeave" />
        </g>

        <!-- x 轴刻度文字 -->
        <g text-anchor="middle" class="chart-label">
          <template v-for="b in bars" :key="'xl' + b.i">
            <text v-if="showLabel(b.i)" :x="b.cx" :y="Y1 + 17">{{ b.label }}</text>
          </template>
        </g>
      </svg>

      <!-- 原型（Chart.js 默认）tooltip：黑底 0.8 / 圆角 6 / 白字 / 彩色小方块，位置缓动 + 淡入淡出 -->
      <div class="cjs-tip" :class="{ 'is-show': tip.show }"
        :style="{ left: tip.x + 'px', top: tip.y + 'px' }">
        <div class="cjs-tip-box">
          <div class="cjs-tip-title">{{ tip.title }}</div>
          <div class="cjs-tip-row"><span class="cjs-tip-swatch" :style="{ background: COLORS.input }"></span>输入: {{ fmtInt(tip.input) }}</div>
          <div class="cjs-tip-row"><span class="cjs-tip-swatch" :style="{ background: COLORS.cached }"></span>命中: {{ fmtInt(tip.cached) }}</div>
          <div class="cjs-tip-row"><span class="cjs-tip-swatch" :style="{ background: COLORS.output }"></span>输出: {{ fmtInt(tip.output) }}</div>
        </div>
        <div class="cjs-tip-caret"></div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  series: { type: Array, default: () => [] },
  windowSeconds: { type: Number, default: 0 },
  windowLabel: { type: String, default: '' },
})

// 坐标系：宽卡自适应，高 240 对齐参考 chart-wrap
const W = 760, H = 240
const X0 = 46, X1 = 752, Y0 = 10, Y1 = 212

const containerRef = ref(null)

// 主题状态色（与全站 green/blue/yellow 状态色一致；红色保留给错误态，本图 3 个系列未用）
const COLORS = {
  input: 'var(--chart-cyan)',   // 输入
  cached: 'var(--chart-green)',  // 命中
  output: 'var(--chart-yellow)', // 输出
}

const fmtK = v => {
  if (v >= 1e6) return (v / 1e6) % 1 === 0 ? (v / 1e6) + 'M' : (v / 1e6).toFixed(1) + 'M'
  if (v >= 1e3) return (v / 1e3) % 1 === 0 ? (v / 1e3) + 'k' : (v / 1e3).toFixed(1) + 'k'
  return String(Math.round(v))
}
const fmtInt = n => (n || 0).toLocaleString()

const data = computed(() => props.series.map(s => ({
  t: s.t || '',
  input: s.input_tokens || 0,
  cached: s.cached_tokens || 0,
  output: s.output_tokens || 0,
})))

// Chart.js 风格 nice ticks：步长取 1/2/5×10^k
const scale = computed(() => {
  const max = Math.max(1, ...data.value.map(d => d.input + d.cached + d.output))
  const rough = max / 5
  const pow = Math.pow(10, Math.floor(Math.log10(rough)))
  let step = pow * 10
  for (const c of [1, 2, 5, 10]) {
    if (rough <= c * pow) { step = c * pow; break }
  }
  const top = Math.ceil(max / step) * step
  const ticks = []
  for (let v = 0; v <= top + step / 1e6; v += step) ticks.push(v)
  return { top, ticks }
})

const yTicks = computed(() =>
  scale.value.ticks.map(v => ({ v, y: Y1 - (v / scale.value.top) * (Y1 - Y0) })).reverse()
)

// barThickness: 15（每个分类槽内居中）
const BAR_W = 15
const RADIUS = 0

const bars = computed(() => {
  const n = data.value.length
  if (!n) return []
  const plotW = X1 - X0
  const slotW = plotW / n
  const k = (Y1 - Y0) / scale.value.top
  return data.value.map((d, i) => {
    const slotX = X0 + i * slotW
    const cx = slotX + slotW / 2
    const bw = Math.min(BAR_W, slotW * 0.9)
    const x = cx - bw / 2
    const inputH = d.input * k
    const cacheH = d.cached * k
    const outputH = d.output * k
    // 堆叠：输入(底) → 命中(中) → 输出(顶)
    const inputY = Y1 - inputH
    const cacheY = inputY - cacheH
    const outputY = cacheY - outputH
    return {
      i, slotX, slotW, cx,
      inputH, cacheH, outputH,
      // 底段：圆底角；中段：方角；顶段：圆顶角（borderSkipped:false）
      inputPath: roundedBar(x, inputY, bw, inputH, RADIUS, { tl: false, tr: false, bl: true, br: true }),
      cachePath: roundedBar(x, cacheY, bw, cacheH, 0, { tl: false, tr: false, bl: false, br: false }),
      outputPath: roundedBar(x, outputY, bw, outputH, RADIUS, { tl: true, tr: true, bl: false, br: false }),
      topY: outputY,
      label: fmtDate(d.t),
      input: d.input, cached: d.cached, output: d.output,
      rawT: d.t,
    }
  })
})

function roundedBar(x, y, w, h, r, c) {
  if (h <= 0) return ''
  r = Math.max(0, Math.min(r, w / 2, h / 2))
  const { tl, tr, bl, br } = c
  let d = `M ${x} ${y + (tl ? r : 0)}`
  if (tl) d += ` A ${r} ${r} 0 0 1 ${x + r} ${y}`
  d += ` L ${x + w - (tr ? r : 0)} ${y}`
  if (tr) d += ` A ${r} ${r} 0 0 1 ${x + w} ${y + r}`
  d += ` L ${x + w} ${y + h - (br ? r : 0)}`
  if (br) d += ` A ${r} ${r} 0 0 1 ${x + w - r} ${y + h}`
  d += ` L ${x + (bl ? r : 0)} ${y + h}`
  if (bl) d += ` A ${r} ${r} 0 0 1 ${x} ${y + h - r}`
  d += ' Z'
  return d
}

function fmtDate(t) {
  if (!t) return ''
  const d = new Date(String(t).replace(' ', 'T'))
  if (isNaN(d.getTime())) return String(t).slice(5, 10)
  if (props.windowSeconds <= 86400) {
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${hh}:${mm}`
  }
  const M = String(d.getMonth() + 1).padStart(2, '0')
  const D = String(d.getDate()).padStart(2, '0')
  return `${M}-${D}`
}

function fmtDateFull(t) {
  if (!t) return ''
  const d = new Date(String(t).replace(' ', 'T'))
  if (isNaN(d.getTime())) return String(t)
  const M = String(d.getMonth() + 1).padStart(2, '0')
  const D = String(d.getDate()).padStart(2, '0')
  if (props.windowSeconds <= 86400) {
    const hh = String(d.getHours()).padStart(2, '0')
    const mm = String(d.getMinutes()).padStart(2, '0')
    return `${M}-${D} ${hh}:${mm}`
  }
  return `${M}-${D}`
}

function showLabel(i) {
  const n = data.value.length
  if (n <= 8) return true
  if (n <= 16) return i % 2 === 0
  if (n <= 32) return i % 4 === 0
  return i % 8 === 0
}

const tip = ref({ show: false, x: 0, y: 0, title: '', input: 0, cached: 0, output: 0 })

function onBarEnter(e, b) {
  const el = containerRef.value
  if (!el) return
  const rect = el.getBoundingClientRect()
  const sx = rect.width / W
  const sy = rect.height / H
  let x = b.cx * sx
  const half = 70
  if (x < half) x = half
  if (x > rect.width - half) x = rect.width - half
  tip.value = {
    show: true,
    x,
    y: Math.max(b.topY * sy, 8),
    title: fmtDateFull(b.rawT),
    input: b.input,
    cached: b.cached,
    output: b.output,
  }
}

function onBarLeave() {
  tip.value.show = false
}
</script>

<style scoped>
/* ═══ 图表区 ═══ */
.chart-wrap {
  position: relative;
  width: 100%;
}
.chart-svg {
  display: block;
  width: 100%;
  height: auto;
}

/* ═══ 原型（Chart.js 默认）tooltip 复刻：位置缓动 + 淡入淡出 ═══ */
.cjs-tip {
  position: absolute;
  z-index: 50;
  pointer-events: none;
  transform: translate(-50%, -100%);
  margin-top: -2px;
  display: flex;
  flex-direction: column;
  align-items: center;
  opacity: 0;
  transition: left 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
              top 0.25s cubic-bezier(0.25, 0.1, 0.25, 1),
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
}
.cjs-tip-caret {
  width: 0;
  height: 0;
  border-left: 5px solid transparent;
  border-right: 5px solid transparent;
  border-top: 5px solid rgba(0, 0, 0, 0.8);
}
</style>
