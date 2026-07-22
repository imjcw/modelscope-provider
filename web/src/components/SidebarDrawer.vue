<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-40 lg:hidden">
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="close"></div>
      <aside class="absolute top-0 left-0 bottom-0 w-56 bg-ls-shell border-r border-ls-border
                    flex flex-col transform transition-transform duration-200"
             :class="isOpen ? 'translate-x-0' : '-translate-x-full exiting'">
        <div class="px-5 py-5">
          <div class="flex items-center gap-2.5">
            <span class="font-bold tracking-tight text-lg">
              <span class="gradient-neon">AI</span>
              <span class="text-ls-text"> Provider</span>
            </span>
          </div>
        </div>
        <SidebarNav @select="close" />
        <div class="px-4 py-3 border-t border-ls-border">
          <div class="flex items-center gap-3 px-1 mb-3">
            <div class="w-7 h-7 rounded-lg bg-ls-border border border-ls-borderLight flex items-center justify-center text-xs font-medium text-ls-text">J</div>
            <div class="flex-1 min-w-0">
              <p class="text-sm font-medium text-ls-text truncate">imjcw</p>
              <p class="text-xs text-ls-muted truncate">admin@modelscope.ai</p>
            </div>
          </div>
          <div class="flex items-center gap-2 mb-2">
            <div class="w-2 h-2 rounded-full bg-green-400"></div>
            <span class="text-xs text-ls-muted">v0.2.0 · 运行中</span>
          </div>
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
