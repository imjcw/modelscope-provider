<script setup>
/**
 * IconButton — 纯图标操作按钮（编辑 / 删除 / 跳转等）。
 * 统一各页面 "text-gray-500 hover:text-white" 系列手写按钮。
 *
 * Usage:
 *   <IconButton icon="edit" title="编辑" @click="openEdit(acc)" />
 *   <IconButton icon="trash" title="删除" tone="danger" padded @click="openDeleteConfirm(key)" />
 *   <IconButton icon="file" title="调用日志" tone="accent" padded @click="openDetailTab(key, 'logs')" />
 */
import CIcon from './CIcon.vue'

defineProps({
  icon: { type: String, required: true },
  title: { type: String, default: '' },
  tone: { type: String, default: 'default' }, // default | danger | accent
  size: { type: [Number, String], default: 14 },
  padded: { type: Boolean, default: false },  // p-1（网格/表格视图）
})

defineEmits(['click'])

const TONE_CLASSES = {
  default: 'text-ls-muted hover:text-ls-text',
  danger: 'text-ls-muted hover:text-red-400',
  accent: 'text-ls-accent hover:text-ls-text',
}
</script>

<template>
  <button type="button" :title="title"
    class="transition-colors"
    :class="[padded && 'p-1', TONE_CLASSES[tone] || TONE_CLASSES.default]"
    @click="$emit('click')">
    <CIcon :name="icon" :size="size" />
  </button>
</template>
