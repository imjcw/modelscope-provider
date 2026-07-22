<script setup>
import { computed } from 'vue'

const props = defineProps({
  input: { type: Number, default: 0 },
  output: { type: Number, default: 0 },
  // cache hit (tokens served from cache). Defaults to 0 for list views
  // that only expose input/output at aggregate level.
  cache: { type: Number, default: 0 },
  // compact mode: tighter spacing for table cells / inline contexts
  compact: { type: Boolean, default: false },
  // plain mode: 无色点，排版与详情面板「模型信息」一致（text-sm + ls-* 颜色）
  plain: { type: Boolean, default: false },
})

const fmt = (n) => (n || 0).toLocaleString()

const cachePct = computed(() => {
  const total = (props.input || 0) + (props.output || 0)
  if (!total) return 0
  return Math.round(((props.cache || 0) / total) * 100)
})

const rowClass = computed(() => [
  'flex items-center justify-between',
  props.plain && 'text-sm',
  props.compact ? 'gap-2' : 'gap-3',
])
const labelClass = computed(() =>
  props.plain ? 'text-ls-dim' : 'text-gray-500 flex items-center gap-1'
)
const valueClass = computed(() =>
  props.plain ? 'text-ls-text font-mono' : 'text-white font-mono'
)
const cacheValueClass = computed(() => {
  if (props.cache > 0) return 'font-mono text-green-400'
  return props.plain ? 'font-mono text-ls-dim' : 'font-mono text-gray-600'
})
</script>

<template>
  <div class="flex flex-col" :class="plain ? 'gap-2' : compact ? 'gap-px' : 'gap-0.5'">
    <div :class="rowClass">
      <span :class="labelClass">
        <span v-if="!plain" class="w-1 h-1 rounded-full bg-blue-400/70"></span>
        输入
      </span>
      <span :class="valueClass">{{ fmt(input) }}</span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">
        <span v-if="!plain" class="w-1 h-1 rounded-full bg-green-400/70"></span>
        Cache命中
      </span>
      <span :class="cacheValueClass">
        {{ fmt(cache) }}<span v-if="cache > 0" class="text-[10px] text-gray-500 ml-0.5">{{ cachePct }}%</span>
      </span>
    </div>
    <div :class="rowClass">
      <span :class="labelClass">
        <span v-if="!plain" class="w-1 h-1 rounded-full bg-amber-400/70"></span>
        输出
      </span>
      <span :class="valueClass">{{ fmt(output) }}</span>
    </div>
  </div>
</template>
