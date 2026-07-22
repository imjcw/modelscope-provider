<script setup>
/**
 * CopyButton — 复制到剪贴板按钮，成功后通过全局 toast 反馈。
 *
 * Usage:
 *   <CopyButton :text="apiBaseUrl" :size="12" />
 *   <CopyButton :text="key" @copied="onCopied" />  页面可监听 copied 做额外动作
 */
import { inject } from 'vue'
import CIcon from './CIcon.vue'

const props = defineProps({
  text: { type: String, default: '' },
  size: { type: [Number, String], default: 14 },
  toastText: { type: String, default: '已复制到剪贴板' },
  colorClass: { type: String, default: 'text-gray-500 hover:text-white' },
})

const emit = defineEmits(['copied'])

const toast = inject('$toast', null)

const copy = () => {
  navigator.clipboard.writeText(props.text).then(() => {
    toast?.(props.toastText, 'success')
    emit('copied')
  }).catch(() => {
    toast?.('复制失败', 'error')
  })
}
</script>

<template>
  <button type="button" class="transition-colors" :class="colorClass" title="复制" @click="copy">
    <CIcon name="copy" :size="size" />
  </button>
</template>
