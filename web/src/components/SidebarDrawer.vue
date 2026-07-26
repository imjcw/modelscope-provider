<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-40 lg:hidden">
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="close"></div>
      <aside class="absolute top-0 left-0 bottom-0 w-56 bg-ls-shell border-r border-ls-border
                    flex flex-col transform transition-transform duration-200"
             :class="isOpen ? 'translate-x-0' : '-translate-x-full exiting'">
        <div class="px-5 py-5">
          <div class="flex items-center gap-2.5">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="var(--ls-accent)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="12" cy="4" r="2"/>
              <circle cx="4" cy="20" r="2"/>
              <circle cx="20" cy="20" r="2"/>
              <circle cx="12" cy="12" r="2"/>
              <line x1="12" y1="6" x2="12" y2="10"/>
              <line x1="5.5" y1="18.5" x2="10.5" y2="13.5"/>
              <line x1="18.5" y1="18.5" x2="13.5" y2="13.5"/>
            </svg>
            <span class="font-bold tracking-tight text-lg">
              <span class="text-ls-accent">A</span><span class="text-ls-text">I</span>
              <span class="text-ls-text">&nbsp;<span class="text-ls-fuchsia">P</span>rovider</span>
            </span>
          </div>
        </div>
        <SidebarNav @select="close" />
        <div class="px-4 py-3 border-t border-ls-border">
          <ThemeToggle />
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import SidebarNav from './SidebarNav.vue'
import ThemeToggle from './ThemeToggle.vue'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])

const visible = ref(false)
const isOpen = ref(false)
const exiting = ref(false)
const exitingTimer = ref(null)

watch(() => props.modelValue, (val) => {
  if (val) {
    visible.value = true
    exiting.value = false
    requestAnimationFrame(() => { isOpen.value = true })
  } else {
    close()
  }
})

function close() {
  if (exiting.value || !visible.value) return
  exiting.value = true
  isOpen.value = false
  clearTimeout(exitingTimer.value)
  exitingTimer.value = setTimeout(() => {
    visible.value = false
    exiting.value = false
    emit('update:modelValue', false)
  }, 200)
}

onBeforeUnmount(() => { clearTimeout(exitingTimer.value) })
</script>
