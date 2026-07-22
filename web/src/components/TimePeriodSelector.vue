<script setup>
/**
 * TimePeriodSelector — styled period picker for time-range filters.
 *
 * Replaces bare native datetime inputs with a segmented preset list
 * (近1小时 / 今天 / 近7天 / 近30天) plus a 自定义 custom-range option.
 *
 * Emits `update` with { start, end } strings in 'YYYY-MM-DD HH:MM:SS'
 * (CST / UTC+8, matching how timestamps are displayed elsewhere).
 * Defaults to 近7天 on mount.
 */

import { ref, onMounted } from 'vue'

const emit = defineEmits(['update'])

const PRESETS = [
  { key: '1h', label: '近1小时' },
  { key: 'today', label: '今天' },
  { key: '7d', label: '近7天' },
  { key: '30d', label: '近30天' },
  { key: 'custom', label: '自定义' },
]

const pad = (n, l = 2) => String(n).padStart(l, '0')

// Format a Date as 'YYYY-MM-DD HH:MM:SS' in CST (UTC+8)
function toCSTStr(d) {
  const cst = new Date(d.getTime() + 8 * 3600000)
  return (
    `${cst.getUTCFullYear()}-${pad(cst.getUTCMonth() + 1)}-${pad(cst.getUTCDate())} ` +
    `${pad(cst.getUTCHours())}:${pad(cst.getUTCMinutes())}:${pad(cst.getUTCSeconds())}`
  )
}

const active = ref('7d')
const customStart = ref('')
const customEnd = ref('')

function rangeFor(key) {
  const now = Date.now()
  let start, end
  switch (key) {
    case '1h':
      start = new Date(now - 3600000); end = new Date(now); break
    case 'today': {
      const cst = new Date(now + 8 * 3600000)
      const y = cst.getUTCFullYear(), m = cst.getUTCMonth(), d = cst.getUTCDate()
      const todayStart = new Date(Date.UTC(y, m, d) - 8 * 3600000)
      const todayEnd = new Date(todayStart.getTime() + 86400000 - 1000)
      start = todayStart; end = todayEnd; break
    }
    case '7d':
      start = new Date(now - 7 * 86400000); end = new Date(now); break
    case '30d':
      start = new Date(now - 30 * 86400000); end = new Date(now); break
    default:
      start = new Date(now - 7 * 86400000); end = new Date(now)
  }
  return { start: toCSTStr(start), end: toCSTStr(end) }
}

function select(key) {
  active.value = key
  if (key !== 'custom') emit('update', rangeFor(key))
}

function onCustom() {
  if (customStart.value && customEnd.value) {
    // datetime-local gives 'YYYY-MM-DDTHH:mm'; pad to full seconds
    const s = customStart.value.replace('T', ' ') + ':00'
    const e = customEnd.value.replace('T', ' ') + ':59'
    emit('update', { start: s, end: e })
  }
}

onMounted(() => emit('update', rangeFor('7d')))
</script>

<template>
  <div class="flex items-center gap-3">
    <!-- Segmented preset pills -->
    <div class="flex bg-ls-bg rounded-lg border border-ls-border p-0.5">
      <button v-for="p in PRESETS" :key="p.key" type="button" @click="select(p.key)"
        class="px-3 h-8 rounded-md text-xs font-medium transition-colors"
        :class="active === p.key
          ? 'bg-ls-elevated text-ls-text'
          : 'text-ls-muted hover:text-ls-text'">
        {{ p.label }}
      </button>
    </div>

    <!-- Custom range (only when 自定义 selected) -->
    <div v-if="active === 'custom'" class="flex items-center gap-2">
      <input type="datetime-local" v-model="customStart" @change="onCustom"
        class="h-8 rounded-lg border border-ls-border bg-ls-bg px-2 text-xs text-ls-text focus:outline-none focus:border-ls-accent" />
      <span class="text-ls-muted text-xs">~</span>
      <input type="datetime-local" v-model="customEnd" @change="onCustom"
        class="h-8 rounded-lg border border-ls-border bg-ls-bg px-2 text-xs text-ls-text focus:outline-none focus:border-ls-accent" />
    </div>
  </div>
</template>
