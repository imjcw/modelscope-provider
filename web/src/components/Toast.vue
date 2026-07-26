<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  message: { type: String, default: '' },
  type: { type: String, default: 'info' },
  duration: { type: Number, default: 3000 },
})
const emit = defineEmits(['update:visible'])

const timer = ref(null)
const clearTimer = () => { if (timer.value) { clearTimeout(timer.value); timer.value = null } }

const close = () => { clearTimer(); emit('update:visible', false) }

watch(() => props.visible, (val) => {
  if (val) { clearTimer(); timer.value = setTimeout(() => close(), props.duration) }
  else { clearTimer() }
})

const colorMap = {
  success: '#a6e3a1',
  error: '#f38ba8',
  warning: '#f9e2af',
  info: 'var(--accent)',
}
const typeColor = () => colorMap[props.type] || colorMap.info
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="toast-enter" :style="{ position: 'fixed', right: '24px', bottom: '24px', zIndex: 100 }">
      <div
        class="flex items-start gap-4 pl-3 py-3 pr-4 rounded-lg border"
        :style="{ backgroundColor: 'var(--surface)', borderColor: 'var(--border)' }"
      >
        <span class="inline-block w-1 h-8 rounded-full flex-shrink-0 mt-0.5" :style="{ backgroundColor: typeColor() }"></span>
        <p class="m-0 text-sm leading-1.5 max-w-xs" :style="{ color: 'var(--text)' }">{{ message }}</p>
        <button
          class="action-icon flex-shrink-0 mt-0.5"
          @click="close"
          :style="{ color: 'var(--text-muted)' }"
          aria-label="Close"
        >
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
@keyframes toastIn {
  from { opacity: 0; transform: translateY(8px) scale(0.96); }
  to   { opacity: 1; transform: translateY(0) scale(1); }
}
.toast-enter { animation: toastIn .2s ease-out; }
</style>
