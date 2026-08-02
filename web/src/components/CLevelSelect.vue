<script setup>
/**
 * CLevelSelect — cascading two-level select (supplier → model).
 *
 * Usage:
 *   <CLevelSelect v-model:level1="supplierId" v-model:level2="model"
 *                 :level1-options="suppliers" :level2-options="modelsBySupplier"
 *                 level1-placeholder="选择供应商" level2-placeholder="选择模型" />
 *
 * Props:
 *   level1Options  — [{ label, value }]   一级选项（供应商）
 *   level2Options  — { [level1Value]: [{ label, value }] }  二级选项映射
 */

import { ref, computed, onMounted, onBeforeUnmount, nextTick } from 'vue'

const props = defineProps({
  level1Options: { type: Array, required: true },
  level2Options: { type: Object, default: () => ({}) },
  level1ModelValue: { type: String, default: '' },
  level2ModelValue: { type: String, default: '' },
  level1Placeholder: { type: String, default: '供应商' },
  level2Placeholder: { type: String, default: '模型' },
})

const emit = defineEmits(['update:level1ModelValue', 'update:level2ModelValue'])

const open = ref(false)
const activeTab = ref('level1') // which column is active
const trigger = ref(null)

const level1Selected = computed(() =>
  props.level1Options.find(o => o.value === props.level1ModelValue) || null,
)
const level2Selected = computed(() => {
  const opts = (props.level2Options)[props.level1ModelValue] || []
  return opts.find(o => o.value === props.level2ModelValue) || null
})

const currentLevel2Options = computed(() =>
  (props.level2Options)[props.level1ModelValue] || [],
)

function selectLevel1(option) {
  emit('update:level1ModelValue', option.value)
  emit('update:level2ModelValue', '') // reset model
  if (currentLevel2Options.value.length) {
    activeTab.value = 'level2'
  } else {
    activeTab.value = 'level1'
  }
}

function selectLevel2(option) {
  emit('update:level2ModelValue', option.value)
  close()
}

function toggle() {
  open.value = !open.value
  activeTab.value = 'level1'
  if (open.value) nextTick(() => positionPopover())
}

function close() {
  open.value = false
  activeTab.value = 'level1'
}

function goBack() {
  activeTab.value = 'level1'
}

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
  <div class="c-level-select" ref="trigger">
    <button
      type="button"
      @click="toggle"
      :class="[
        'w-full text-left inline-flex items-center gap-2 px-3 py-2',
        'h-8 bg-ls-bg rounded-lg border border-ls-border',
        'text-ls-text placeholder:text-ls-muted',
        'focus:outline-none focus:border-ls-accent',
        'transition-all duration-200 text-xs',
        open ? 'border-ls-accent' : '',
      ]"
    >
      <!-- Level 1: supplier -->
      <span class="flex items-center gap-1.5 flex-shrink-0">
        <span class="text-ls-muted">{{ level1Placeholder }}</span>
        <span class="truncate inline-block"
          :class="level1Selected ? 'text-ls-text' : 'text-ls-muted'">
          {{ level1Selected ? level1Selected.label : '全部' }}
        </span>
      </span>

      <!-- Divider -->
      <span class="text-ls-dim">/</span>

      <!-- Level 2: model -->
      <span class="flex items-center gap-1.5 flex-1 min-w-0">
        <span class="text-ls-muted">{{ level2Placeholder }}</span>
        <span class="truncate inline-block"
          :class="level2Selected ? 'text-ls-text' : 'text-ls-muted'">
          {{ level2Selected ? level2Selected.label : '全部' }}
        </span>
      </span>

      <!-- Chevron -->
      <svg
        width="12" height="12" viewBox="0 0 24 24"
        fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round"
        class="text-ls-muted transition-transform duration-200 flex-shrink-0"
        :class="open ? 'rotate-180' : ''"
      >
        <polyline points="6 9 12 15 18 9"></polyline>
      </svg>
    </button>

    <Teleport to="body">
      <div v-if="open"
        class="c-level-popover"
        :style="popoverStyle"
        @click.stop
      >
        <div class="bg-ls-card border border-ls-border rounded-lg py-1.5 animate-in max-h-80 overflow-y-auto">
          <!-- Level 1: Suppliers -->
          <template v-if="activeTab === 'level1'">
            <div class="px-3 py-1.5 text-[10px] text-ls-dim font-mono uppercase tracking-wider">
              {{ level1Placeholder }}
            </div>
            <button type="button"
              @click="selectLevel1({ value: '', label: level1Placeholder + '-全部' })"
              class="w-full text-left px-3 py-1.5 text-xs transition-colors duration-100 overflow-hidden"
              :class="!level1Selected ? 'bg-ls-accent/10 text-ls-accent' : 'text-ls-text hover:bg-ls-elevated'">
              <span class="truncate inline-block">全部</span>
            </button>
            <button v-for="opt in level1Options" :key="opt.value" type="button"
              @click="selectLevel1(opt)"
              class="w-full text-left px-3 py-1.5 text-xs transition-colors duration-100 overflow-hidden"
              :class="opt.value === level1ModelValue
                ? 'bg-ls-accent/10 text-ls-accent'
                : 'text-ls-text hover:bg-ls-elevated'">
              <span class="truncate inline-block">{{ opt.label }}</span>
            </button>
          </template>

          <!-- Level 2: Models -->
          <template v-else>
            <div class="flex items-center gap-1.5 px-3 py-1.5 border-b border-ls-border mb-1">
              <button @click="goBack"
                class="text-ls-muted hover:text-ls-text transition-colors flex items-center gap-1 text-xs">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                  stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <polyline points="15 18 9 12 15 6"/>
                </svg>
                {{ level1Selected?.label || level1Placeholder }}
              </button>
            </div>
            <button type="button"
              @click="selectLevel2({ value: '', label: level2Placeholder + '-全部' })"
              class="w-full text-left px-3 py-1.5 text-xs transition-colors duration-100 overflow-hidden"
              :class="!level2Selected ? 'bg-ls-accent/10 text-ls-accent' : 'text-ls-text hover:bg-ls-elevated'">
              <span class="truncate inline-block">全部</span>
            </button>
            <button v-for="opt in currentLevel2Options" :key="opt.value" type="button"
              @click="selectLevel2(opt)"
              class="w-full text-left px-3 py-1.5 text-xs transition-colors duration-100 overflow-hidden"
              :class="opt.value === level2ModelValue
                ? 'bg-ls-accent/10 text-ls-accent'
                : 'text-ls-text hover:bg-ls-elevated'">
              <span class="truncate inline-block">{{ opt.label }}</span>
            </button>
          </template>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.c-level-popover {
  position: fixed;
  z-index: 70;
  animation: popoverIn .15s ease-out;
}

@keyframes popoverIn {
  from { opacity: 0; transform: translateY(-4px); }
  to   { opacity: 1; transform: translateY(0); }
}

:global(body:has(.c-level-popover)) {
  overflow: hidden;
}
</style>
