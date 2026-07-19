<script setup>
/**
 * Drawer — 右侧滑入/滑出抽屉 (朴素风格)。
 * - 颜色遵循 Catppuccin-Mocha 暗色 theme，无额外配色
 * - 进入/退出通过 `exiting` ref 驱动 CSS 过渡
 * - 点击遮罩 / ESC 键关闭
 */
import { ref, watch, onMounted, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '780px' },
  noHeader: { type: Boolean, default: false },
  responsive: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const exiting = ref(false)
const exitingTimer = ref(null)

const close = () => {
  if (exiting.value) return
  exiting.value = true
  exitingTimer.value = setTimeout(() => {
    visible.value = false
    exiting.value = false
    emit('update:modelValue', false)
  }, 250)
}

watch(
  () => props.modelValue,
  (val) => {
    if (val) {
      visible.value = true
      exiting.value = false
    } else {
      close()
    }
  }
)

const handleEsc = (e) => {
  if (e.key === 'Escape' && visible.value && !exiting.value) {
    close()
    e.stopImmediatePropagation()
  }
}

onMounted(() => document.addEventListener('keydown', handleEsc))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEsc)
  if (exitingTimer.value) clearTimeout(exitingTimer.value)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="drawer-overlay" @click.self="close">
      <div class="drawer drawer-right"
           :class="{ 'drawer-responsive': responsive }"
           :style="responsive ? { '--drawer-width': props.width } : { width: props.width }">
        <div class="drawer-panel" :class="{ 'exiting': exiting }">
          <div v-if="!noHeader" class="drawer-header">
            <h2 class="drawer-title">{{ title }}</h2>
            <button @click="close" class="drawer-close btn-esc">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="drawer-body" :class="{ 'is-full': noHeader }"><slot></slot></div>
          <div v-if="$slots.footer" class="drawer-footer"><slot name="footer"></slot></div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
