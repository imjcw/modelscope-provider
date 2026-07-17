<script setup>
import { watch, onBeforeUnmount } from 'vue'
import { useOverlayEsc } from '@/composables/useOverlayEsc'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  title: { type: String, default: '确认' },
  message: { type: String, default: '' },
  danger: { type: Boolean, default: false },
  confirmText: { type: String, default: '确认' },
  cancelText: { type: String, default: '取消' },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue', 'confirm'])

const { register, unregister } = useOverlayEsc()

const handleConfirm = () => {
  emit('confirm')
  close()
}

const close = () => {
  unregister(escId)
  emit('update:modelValue', false)
}

let escId = null

watch(
  () => props.modelValue,
  (val) => {
    if (val) escId = register({ close, confirm: handleConfirm })
    else { unregister(escId); escId = null }
  }
)

onBeforeUnmount(() => {
  if (escId) unregister(escId)
})
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="modal-overlay" @click.self="close">
      <div class="modal">
        <div class="modal-icon" :class="danger ? 'modal-icon-danger' : 'modal-icon-warning'">
          <svg v-if="danger" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
            <path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
          </svg>
          <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
            <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
          </svg>
        </div>
        <h3 class="modal-title">{{ title }}</h3>
        <p class="modal-message" v-html="message"></p>
        <div class="modal-actions">
          <button @click="close" class="btn btn-secondary btn-esc">{{ cancelText }}</button>
          <button @click="handleConfirm" class="btn" :class="danger ? 'btn-danger' : 'btn-primary'" :disabled="disabled">
            {{ confirmText }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>
