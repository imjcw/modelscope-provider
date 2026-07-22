<script setup>
/**
 * StatusCodeBadge — HTTP 状态码徽章：≥500 红 / ≥400 黄 / 其余绿。
 * 对齐 demo/cyberpunk-dark.html 的 HTTP 状态码徽章：
 *   bg-green-500/10 text-green-400 border border-green-500/20 rounded
 */
import { computed } from 'vue'

const props = defineProps({
  code: { type: Number, default: 0 },
  small: { type: Boolean, default: false },
  padded: { type: Boolean, default: false },
})

const toneClass = computed(() =>
  props.code >= 500 ? 'bg-red-500/10 text-red-400 border border-red-500/20'
  : props.code >= 400 ? 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20'
  : 'bg-green-500/10 text-green-400 border border-green-500/20'
)
</script>

<template>
  <span class="inline-flex items-center rounded-md py-0.5"
    :class="[padded ? 'px-2' : 'px-1.5', small && 'text-xs', toneClass]">
    {{ code }}
  </span>
</template>
