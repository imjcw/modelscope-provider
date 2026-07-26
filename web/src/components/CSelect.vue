<script setup>
/**
 * CSelect — styled replacement for native <select>.
 *
 * Usage:
 *   <CSelect v-model="value" :options="opts" placeholder="Choose…" />
 *
 * Props:
 *   options    — array of { label, value }
 *   modelValue
 *   placeholder
 *   size       — 'sm' | 'md' (default) | 'lg'
 */

import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  options: { type: Array, required: true },
  modelValue: { type: [String, Number, Boolean], default: '' },
  placeholder: { type: String, default: '请选择' },
  size: { type: String, default: 'md' },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const trigger = ref(null)

const selectedOption = computed(() =>
  props.options.find(o => o.value === props.modelValue) || null,
)

const sizeClasses = {
  sm: 'h-8 text-xs px-2.5',
  md: 'h-10 text-sm px-3',
  lg: 'h-12 text-sm px-4',
}

function select(option) {
  emit('update:modelValue', option.value)
  close()
}

function toggle() {
  open.value = !open.value
  if (open.value) nextTick(() => positionPopover())
}

function close() {
  open.value = false
}

// Click-outside handler
const handleClickOutside = (e) => {
  if (trigger.value && !trigger.value.contains(e.target)) {
    close()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})
onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
})

// Popover positioning
const popoverStyle = ref({})

function positionPopover() {
  if (!trigger.value) return
  const rect = trigger.value.getBoundingClientRect()
  const scrollTop = window.scrollY || document.documentElement.scrollTop
  const scrollLeft = window.scrollX || document.documentElement.scrollLeft
  popoverStyle.value = {
    top: (rect.bottom + scrollTop + 6) + 'px',
    left: (rect.left + scrollLeft) + 'px',
    width: rect.width + 'px',
  }
}
</script>

<template>
  <div class="c-select" ref="trigger">
    <!-- Trigger button -->
    <button
      type="button"
      @click="toggle"
      :class="[
        'c-select-trigger',
        sizeClasses[size] || sizeClasses.md,
        'w-full text-left inline-flex items-center justify-between',
    'bg-ls-bg rounded-lg border border-ls-border',
    'text-ls-text placeholder:text-ls-muted',
    'focus:outline-none focus:border-ls-accent',
    'transition-all duration-200',
    open ? 'border-ls-accent' : '',
      ]"
    >
      <span class="truncate" :class="selectedOption ? 'text-ls-text' : 'text-ls-muted'">
        {{ selectedOption ? selectedOption.label : placeholder }}
      </span>
      <svg
        width="14" height="14" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"
        class="text-ls-muted transition-transform duration-200 flex-shrink-0 ml-2"
        :class="open ? 'rotate-180' : ''"
      >
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <!-- Popover (Teleported to body for z-index and positioning) -->
    <Teleport to="body">
      <div
        v-if="open"
        class="c-select-popover"
        :style="popoverStyle"
        @click.stop
      >
        <div class="bg-ls-card border border-ls-border rounded-lg py-1.5 animate-in">
          <button
            v-for="(option, i) in options"
            :key="i"
            type="button"
            @click="select(option)"
            class="w-full text-left px-3 py-2 text-sm transition-colors duration-100"
            :class="
              option.value === modelValue
                ? 'bg-ls-accent/10 text-ls-accent'
                : 'text-ls-text hover:bg-ls-elevated'
            "
          >
            <span class="truncate">{{ option.label }}</span>
          </button>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.c-select-popover {
  position: fixed;
  z-index: 70;
  animation: popoverIn .15s ease-out;
}

@keyframes popoverIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Prevent body scroll while popover is open */
:global(body:has(.c-select-popover)) {
  overflow: hidden;
}
</style>
