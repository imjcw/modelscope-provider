<script setup>
/**
 * Avatar — 首字母方块头像（供应商 / API Key 名称前两位大写）。
 *
 * Usage:
 *   <Avatar :text="acc.name" />              卡片行 / 网格（w-10）
 *   <Avatar :text="acc.name" size="sm" />    表格（w-8）
 *   <Avatar :text="key.name" accent />       API Key（蓝色字母）
 */
import { computed } from 'vue'

const props = defineProps({
  text: { type: String, default: '' },
  size: { type: String, default: 'md' }, // md = w-10 | sm = w-8
  accent: { type: Boolean, default: false },
})

const initials = computed(() => (props.text || '').slice(0, 2).toUpperCase())
</script>

<template>
  <div class="rounded-md bg-ls-elevated flex items-center justify-center flex-shrink-0"
    :class="size === 'sm' ? 'w-8 h-8' : 'w-10 h-10'">
    <span class="font-semibold"
      :class="[size === 'sm' ? 'text-xs' : 'text-sm', accent ? 'text-ls-accent' : 'text-ls-dim']">
      {{ initials }}
    </span>
  </div>
</template>
