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
})

const fmt = (n) => (n || 0).toLocaleString()

const cachePct = computed(() => {
  const total = (props.input || 0) + (props.output || 0)
  if (!total) return 0
  return Math.round(((props.cache || 0) / total) * 100)
})
</script>

<template>
  <div class="flex flex-col" :class="compact ? 'gap-px' : 'gap-0.5'">
    <div class="flex items-center justify-between" :class="compact ? 'gap-2' : 'gap-3'">
      <span class="text-gray-500 flex items-center gap-1">
        <span class="w-1 h-1 rounded-full bg-blue-400/70"></span>
        输入
      </span>
      <span class="text-white font-mono">{{ fmt(input) }}</span>
    </div>
    <div class="flex items-center justify-between" :class="compact ? 'gap-2' : 'gap-3'">
      <span class="text-gray-500 flex items-center gap-1">
        <span class="w-1 h-1 rounded-full bg-green-400/70"></span>
        Cache命中
      </span>
      <span class="font-mono" :class="cache > 0 ? 'text-green-400' : 'text-gray-600'">
        {{ fmt(cache) }}<span v-if="cache > 0" class="text-[10px] text-gray-500 ml-0.5">{{ cachePct }}%</span>
      </span>
    </div>
    <div class="flex items-center justify-between" :class="compact ? 'gap-2' : 'gap-3'">
      <span class="text-gray-500 flex items-center gap-1">
        <span class="w-1 h-1 rounded-full bg-amber-400/70"></span>
        输出
      </span>
      <span class="text-white font-mono">{{ fmt(output) }}</span>
    </div>
  </div>
</template>
