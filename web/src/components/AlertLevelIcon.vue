<script setup>
/**
 * AlertLevelIcon — 告警级别图标（warning / error / critical / info / recovered）。
 * simple 模式输出表格视图里的简化图形（仅外框，无内部线条）。
 *
 * Usage:
 *   <AlertLevelIcon :level="alert.level" />
 *   <AlertLevelIcon :level="alert.level" simple :size="12" />
 */
import CIcon from './CIcon.vue'

defineProps({
  level: { type: String, default: '' },
  simple: { type: Boolean, default: false },
  size: { type: [Number, String], default: 14 },
})
</script>

<template>
  <CIcon v-if="level === 'warning'"
    :name="simple ? 'alert-triangle-simple' : 'alert-triangle'" :size="size" class="text-yellow-400" />
  <CIcon v-else-if="level === 'error' || level === 'critical'"
    :name="simple ? 'x-circle-simple' : 'x-circle'" :size="size" class="text-red-400" />
  <CIcon v-else-if="level === 'info'"
    :name="simple ? 'info-simple' : 'info'" :size="size" class="text-ls-accent" />
  <CIcon v-else name="check-circle" :size="size" class="text-green-400" />
</template>
