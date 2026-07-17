<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '' },
  width: { type: String, default: '780px' },
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

const closeImmediate = () => {
  if (exitingTimer.value) clearTimeout(exitingTimer.value)
  visible.value = false
  exiting.value = false
  emit('update:modelValue', false)
}

// 监听 props.modelValue 变化
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
  if (e.key === 'Escape' && visible.value) close()
}

watch(visible, (val) => {
  if (val) document.addEventListener('keydown', handleEsc)
  else document.removeEventListener('keydown', handleEsc)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', handleEsc)
  if (exitingTimer.value) clearTimeout(exitingTimer.value)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="drawer-overlay">
      <div class="drawer drawer-right" :style="{ width: props.width }">
        <div class="drawer-panel" :class="{ 'exiting': exiting }">
          <div class="drawer-header">
            <h2 class="drawer-title">{{ title }}</h2>
            <button @click="close" class="drawer-close btn-esc">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
          <div class="drawer-body">
            <slot></slot>
          </div>
          <div v-if="$slots.footer" class="drawer-footer">
            <slot name="footer"></slot>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
