<template>
  <Teleport to="body">
    <div v-if="visible" class="fixed inset-0 z-40 lg:hidden">
      <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="close"></div>
      <aside class="absolute top-0 left-0 bottom-0 w-56 bg-ls-bg border-r border-ls-border
                    flex flex-col transform transition-transform duration-200"
             :class="isOpen ? 'translate-x-0' : '-translate-x-full exiting'">
        <div class="px-5 py-5">
          <div class="flex items-center gap-2.5">
            <div class="w-7 h-7 rounded-lg bg-[#0c0c0c] border border-gray-800 flex items-center justify-center font-bold text-[11px] tracking-tight">
              <span class="text-ls-accent">A</span><span class="text-[#89b4fa]">P</span>
            </div>
            <span class="font-semibold tracking-tight text-sm">
              <span class="text-ls-accent">A</span><span class="text-white">I</span>
              <span class="text-white">&nbsp;</span>
              <span class="text-[#89b4fa]">P</span><span class="text-white">rovider</span>
            </span>
          </div>
        </div>
        <SidebarNav @select="close" />
        <div class="px-4 py-3 border-t border-ls-border">
          <div class="flex items-center gap-2">
            <div class="w-2 h-2 rounded-full bg-ls-accent"></div>
            <span class="text-xs text-gray-500">v0.2.0 · 运行中</span>
          </div>
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup>
import { ref, watch, onBeforeUnmount } from 'vue'
import SidebarNav from './SidebarNav.vue'

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
