<script setup>
import { ref } from 'vue'

/**
 * CCheckbox — toggle switch styled checkbox with accessible keyboard support.
 *
 * Usage:
 *   <CCheckbox v-model="checked" :disabled="false" />
 *
 * Props:
 *   modelValue — boolean, checked state
 *   disabled   — boolean, disabled state
 */

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(['update:modelValue'])

const toggle = () => {
  if (!props.disabled) {
    emit('update:modelValue', !props.modelValue)
  }
}

// ── Keyboard support ──
const handleKey = (e) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault()
    toggle()
  }
}

const checkboxRef = ref(null)

const focusCheckbox = () => {
  checkboxRef.value?.focus()
}
</script>

<template>
  <div
    ref="checkboxRef"
    class="c-toggle"
    :class="{ 'c-toggle-checked': modelValue, 'c-toggle-disabled': disabled }"
    role="switch"
    :aria-checked="modelValue"
    :aria-disabled="disabled"
    :tabindex="disabled ? -1 : 0"
    @click="toggle"
    @keydown="handleKey"
    title="启用/禁用"
  >
    <div class="c-toggle-track"></div>
    <div class="c-toggle-thumb"></div>
  </div>
</template>

<style scoped>
.c-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  width: 36px;
  height: 20px;
  border-radius: 10px;
  background: var(--ls-elevated);
  cursor: pointer;
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
  flex-shrink: 0;
  outline: none;
}

/* Track styles */
.c-toggle-track {
  position: absolute;
  inset: 0;
  border-radius: 10px;
  transition: background 200ms ease;
}

.c-toggle-checked {
  background: var(--ls-accent);
}

/* Thumb (circle) */
.c-toggle-thumb {
  position: absolute;
  top: 2px;
  left: 2px;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--text-muted);
  transition: all 200ms cubic-bezier(0.4, 0, 0.2, 1);
}

.c-toggle-checked .c-toggle-thumb {
  left: 18px;
  background: white;
}

/* Hover effect */
.c-toggle:not(.c-toggle-disabled):hover .c-toggle-thumb {
  background: var(--text-dim);
}

.c-toggle-checked:not(.c-toggle-disabled):hover .c-toggle-thumb {
  background: white;
}

/* Focus state */
.c-toggle:focus-visible {
  outline: 2px solid var(--ls-accent);
  outline-offset: 2px;
}

/* Disabled state */
.c-toggle-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.c-toggle-disabled .c-toggle-thumb {
  background: var(--text-muted);
}
</style>
