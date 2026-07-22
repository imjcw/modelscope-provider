<script setup>
/**
 * SegmentedControl — 胶囊式分段选择器。
 * 统一 Logs「定时刷新」与 LogPanel「时间范围」的手写按钮组。
 *
 * variant="neon"：Dashboard 头部时间窗变体，精确对齐 demo 的分段按钮
 * （10px 大写宽字距、active 实底），样式在 main.css 的 .seg-neon。
 *
 * Usage:
 *   <SegmentedControl v-model="refreshInterval" :options="REFRESH_OPTIONS" />
 *   <SegmentedControl v-model="days" :options="DAYS_OPTIONS" size="sm" />
 *   <SegmentedControl v-model="windowSeconds" :options="WINDOW_OPTIONS" variant="neon" />
 */
defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, required: true }, // [{ label, value }]
  size: { type: String, default: 'md' },    // md = h-8 | sm = h-7
  variant: { type: String, default: 'default' }, // default | neon
})

const emit = defineEmits(['update:modelValue'])
</script>

<template>
  <div v-if="variant === 'neon'" class="seg-neon">
    <button v-for="opt in options" :key="opt.value" type="button"
      @click="emit('update:modelValue', opt.value)"
      :class="{ active: modelValue === opt.value }">
      {{ opt.label }}
    </button>
  </div>
  <div v-else class="flex bg-ls-card rounded-lg border border-ls-border p-0.5">
    <button v-for="opt in options" :key="opt.value" type="button"
      @click="emit('update:modelValue', opt.value)"
      class="px-2.5 rounded-md text-xs font-medium transition-colors"
      :class="[size === 'sm' ? 'h-7' : 'h-8',
        modelValue === opt.value ? 'bg-ls-elevated text-white' : 'text-gray-500 hover:text-white']">
      {{ opt.label }}
    </button>
  </div>
</template>
