<script setup>
/**
 * DateRangePicker — custom date-range selector (no native inputs).
 *
 * Trigger mimics the CSelect trigger so it sits flush with the other filter
 * controls. Clicking it opens a popover:
 *   • left column  — quick shortcuts (今天 / 近7天 / 近30天 / 本月 / 上月 ...)
 *   • right column — dual-month calendar with range highlighting
 *
 * Emits `update` with { start, end } as 'YYYY-MM-DD HH:MM:SS' strings
 * (start at 00:00:00, end at 23:59:59). Defaults to a 7-day span ending today.
 */

import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'

const emit = defineEmits(['update'])

const pad = (n) => String(n).padStart(2, '0')
const ymd = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const dateOnly = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate())

// ── Popover open / positioning (same pattern as CSelect) ──
const open = ref(false)
const trigger = ref(null)
const popoverStyle = ref({})

function toggle() {
  open.value = !open.value
  if (open.value) {
    picking.value = 'start' // 每次打开都从「选开始日」开始，与提示文案一致
    nextTick(positionPopover)
  }
}
function close() { open.value = false }
function positionPopover() {
  if (!trigger.value) return
  const r = trigger.value.getBoundingClientRect()
  const st = window.scrollY || document.documentElement.scrollTop
  const sl = window.scrollX || document.documentElement.scrollLeft
  popoverStyle.value = {
    top: (r.bottom + st + 6) + 'px',
    left: (r.left + sl) + 'px',
  }
}
const onOutside = (e) => { if (trigger.value && !trigger.value.contains(e.target)) close() }
onMounted(() => document.addEventListener('click', onOutside))
onBeforeUnmount(() => document.removeEventListener('click', onOutside))

// ── Range state (Date at midnight) ──
const today = dateOnly(new Date())
const start = ref(new Date(today.getTime() - 6 * 86400000)) // 7-day span inclusive
const end = ref(today)
const picking = ref('start') // which boundary the next calendar click sets
const hover = ref(null)

// clickDate / applyShortcut 都保证 start <= end，这里只负责透出
function emitRange() {
  emit('update', {
    start: `${ymd(start.value)} 00:00:00`,
    end: `${ymd(end.value)} 23:59:59`,
  })
}

// ── Shortcuts ──
const SHORTCUTS = [
  { label: '今天', range: () => [today, today] },
  { label: '昨天', range: () => [shift(today, -1), shift(today, -1)] },
  { label: '近7天', range: () => [shift(today, -6), today] },
  { label: '近30天', range: () => [shift(today, -29), today] },
  { label: '本月', range: () => [new Date(today.getFullYear(), today.getMonth(), 1), today] },
  { label: '上月', range: () => {
    const e = new Date(today.getFullYear(), today.getMonth(), 0)
    return [new Date(e.getFullYear(), e.getMonth(), 1), e]
  } },
]
function shift(d, days) { return new Date(d.getTime() + days * 86400000) }
function applyShortcut(fn) {
  const [s, e] = fn()
  start.value = s; end.value = e; picking.value = 'start' // 快捷方式已产生完整范围，下次点击重新开始选
  emitRange()
}

// ── Dual-month calendar ──
// `leftAnchor` is the month (year, month-0) shown on the left; right = +1 month.
const leftAnchor = ref({ y: today.getFullYear(), m: today.getMonth() })

const MONTHS = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']
const WEEKDAYS = ['一','二','三','四','五','六','日'] // Mon-first

function gridFor(year, month) {
  const first = new Date(year, month, 1)
  const total = new Date(year, month + 1, 0).getDate()
  const lead = (first.getDay() + 6) % 7 // blanks before Monday
  const cells = []
  for (let i = 0; i < lead; i++) cells.push(null)
  for (let d = 1; d <= total; d++) cells.push(new Date(year, month, d))
  while (cells.length % 7 !== 0) cells.push(null)
  return cells
}
function shiftMonth(y, m, delta) {
  const d = new Date(y, m + delta, 1)
  return { y: d.getFullYear(), m: d.getMonth() }
}
const leftGrid = computed(() => gridFor(leftAnchor.value.y, leftAnchor.value.m))
const rightMonth = computed(() => shiftMonth(leftAnchor.value.y, leftAnchor.value.m, 1))
const rightGrid = computed(() => gridFor(rightMonth.value.y, rightMonth.value.m))

function prev() { leftAnchor.value = shiftMonth(leftAnchor.value.y, leftAnchor.value.m, -2) }
function next() { leftAnchor.value = shiftMonth(leftAnchor.value.y, leftAnchor.value.m, 2) }

// cell style helpers
const inRange = (d) => d && d >= start.value && d <= end.value
const isStart = (d) => d && d.getTime() === start.value.getTime()
const isEnd = (d) => d && d.getTime() === end.value.getTime()
const isHoverBetween = (d) => {
  // 只在「选结束日」阶段预览悬停范围，避免第一次点击前误导
  if (!d || !hover.value || picking.value !== 'end') return false
  const lo = Math.min(start.value.getTime(), hover.value.getTime())
  const hi = Math.max(start.value.getTime(), hover.value.getTime())
  return d.getTime() > lo && d.getTime() < hi
}

function clickDate(d) {
  if (!d) return
  if (picking.value === 'start') {
    // 第一次点击：设开始日，范围暂收为单日，等第二次点击设结束日
    start.value = d
    end.value = d
    picking.value = 'end'
  } else {
    // 第二次点击：设结束日；若早于开始日，视为反选，整体调换
    if (d.getTime() < start.value.getTime()) {
      end.value = start.value
      start.value = d
    } else {
      end.value = d
    }
    picking.value = 'start'
  }
  emitRange()
}

// display text in the trigger
const displayText = computed(() => `${ymd(start.value)} ~ ${ymd(end.value)}`)

// initial emit
onMounted(() => emitRange())
</script>

<template>
  <div class="c-select" ref="trigger">
    <!-- Trigger (matches CSelect trigger) -->
    <button type="button" @click="toggle"
      class="h-8 text-xs px-2.5 w-full text-left inline-flex items-center justify-between bg-ls-bg rounded-lg border border-ls-border text-ls-text placeholder:text-ls-muted focus:outline-none focus:border-ls-accent focus:ring-1 focus:ring-ls-accent/20 transition-all"
      :class="open ? 'border-ls-accent ring-1 ring-ls-accent/20' : ''">
      <span class="truncate inline-flex items-center gap-1.5">
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-ls-muted flex-shrink-0">
          <rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/>
        </svg>
        {{ displayText }}
      </span>
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="text-ls-muted transition-transform flex-shrink-0 ml-2" :class="open ? 'rotate-180' : ''">
        <polyline points="6 9 12 15 18 9"/>
      </svg>
    </button>

    <!-- Popover -->
    <Teleport to="body">
      <div v-if="open" class="c-select-popover" :style="popoverStyle" @click.stop>
        <div class="flex bg-ls-card border border-ls-border rounded-xl shadow-xl shadow-black/40 overflow-hidden animate-in">

          <!-- ── Left: quick shortcuts ── -->
          <div class="w-28 py-2 border-r border-ls-border flex-shrink-0">
            <button v-for="s in SHORTCUTS" :key="s.label" type="button" @click="applyShortcut(s.range)"
              class="w-full text-left px-3 py-2 text-xs transition-colors text-ls-dim hover:bg-ls-elevated hover:text-ls-text">
              {{ s.label }}
            </button>
          </div>

          <!-- ── Right: dual-month calendar ── -->
          <div class="p-3 w-[460px]">
            <!-- header / nav -->
            <div class="flex items-center justify-between mb-2">
              <button type="button" @click="prev" class="w-7 h-7 rounded-md text-ls-dim hover:text-ls-text hover:bg-ls-elevated flex items-center justify-center">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="15 18 9 12 15 6"/></svg>
              </button>
              <span class="text-xs text-ls-dim">{{ leftAnchor.y }}年 {{ MONTHS[leftAnchor.m] }}  {{ rightMonth.y }}年 {{ MONTHS[rightMonth.m] }}</span>
              <button type="button" @click="next" class="w-7 h-7 rounded-md text-ls-dim hover:text-ls-text hover:bg-ls-elevated flex items-center justify-center">
                <svg width="14" height="14" viewBox="00 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="9 18 15 12 9 6"/></svg>
              </button>
            </div>

            <!-- weekday headers (shared axis above both months) -->
            <div class="grid grid-cols-2 gap-3 mb-1">
              <div v-for="(label, idx) in [MONTHS[leftAnchor.m] + ' ' + leftAnchor.y, MONTHS[rightMonth.m] + ' ' + rightMonth.y]" :key="idx">
                <div class="text-[11px] text-ls-dim font-medium mb-1">{{ label }}</div>
              </div>
            </div>

            <!-- weekday glyphs + two month grids -->
            <div class="grid grid-cols-2 gap-3">
              <div v-for="(grid, idx) in [leftGrid, rightGrid]" :key="idx">
                <div class="grid grid-cols-7">
                  <div v-for="w in WEEKDAYS" :key="w" class="text-center text-[10px] text-ls-muted py-1">{{ w }}</div>
                </div>
                <div class="grid grid-cols-7">
                  <div v-for="(d, ci) in grid" :key="ci" class="h-8 py-0.5">
                    <button v-if="d" type="button"
                      @click="clickDate(d)"
                      @mouseenter="hover = d"
                      @mouseleave="hover = null"
                      class="w-full h-7 rounded-md text-xs flex items-center justify-center transition-colors relative"
                      :class="[
                        isStart(d) || isEnd(d) ? 'bg-ls-accent text-ls-bg font-semibold' :
                        inRange(d) || isHoverBetween(d) ? 'bg-ls-accent/15 text-ls-text' :
                        d.getTime() === today.getTime() ? 'ring-1 ring-ls-accent/50 text-ls-text' :
                        'text-ls-dim hover:bg-ls-elevated',
                      ]">
                      {{ d.getDate() }}
                    </button>
                  </div>
                </div>
              </div>
            </div>

            <!-- footnote -->
            <div class="mt-3 flex items-center justify-between text-[10px] text-ls-muted">
              <span>点击选开始日期，再次点击选结束日期</span>
              <button type="button" @click="applyShortcut(SHORTCUTS[2].range)" class="text-ls-accent hover:underline">重置为近7天</button>
            </div>

          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.c-select-popover { position: fixed; z-index: 70; animation: popoverIn .15s ease-out; }
@keyframes popoverIn { from { opacity: 0; transform: translateY(-4px); } to { opacity: 1; transform: translateY(0); } }
</style>
