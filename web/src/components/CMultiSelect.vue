<script setup>
/**
 * CMultiSelect — 多选下拉（从 Mappings「绑定模型」手写实现抽出）。
 * 交互沿用 CSelect 模式：点击展开、点外部关闭；选项支持 extra 副标签。
 *
 * Usage:
 *   <CMultiSelect v-model="selectedModels" :options="modelOptions"
 *     placeholder="选择模型" empty-text="该供应商暂无模型" />
 *   options: [{ label, value, extra }]
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import CIcon from './CIcon.vue'

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  options: { type: Array, required: true },
  placeholder: { type: String, default: '请选择' },
  emptyText: { type: String, default: '暂无选项' },
})

const emit = defineEmits(['update:modelValue'])

const open = ref(false)
const rootRef = ref(null)

const isSelected = (value) => props.modelValue.includes(value)

const toggleValue = (value) => {
  const next = [...props.modelValue]
  const idx = next.indexOf(value)
  if (idx >= 0) next.splice(idx, 1)
  else next.push(value)
  emit('update:modelValue', next)
}

// 点击外部关闭下拉
const handleClickOutside = (e) => {
  if (rootRef.value && !rootRef.value.contains(e.target)) open.value = false
}

onMounted(() => document.addEventListener('click', handleClickOutside))
onBeforeUnmount(() => document.removeEventListener('click', handleClickOutside))
</script>

<template>
  <div class="relative" ref="rootRef">
    <button type="button" @click="open = !open"
      class="form-input text-left flex items-center justify-between"
      :class="{ 'border-ls-accent': open }">
      <span class="truncate" :class="modelValue.length ? 'text-ls-text' : 'text-ls-muted'">
        <span v-if="modelValue.length">{{ modelValue.length }} 个已选</span>
        <span v-else>{{ placeholder }}</span>
      </span>
      <CIcon name="chevron-down"
        class="text-ls-muted transition-transform flex-shrink-0 ml-2"
        :class="open ? 'rotate-180' : ''" />
    </button>

    <!-- 多选下拉列表 -->
    <div v-if="open"
      class="absolute z-30 top-full left-0 right-0 mt-1 bg-ls-card border border-ls-border rounded-lg shadow-lg shadow-black/30 max-h-48 overflow-y-auto">
      <div v-if="options.length === 0" class="px-3 py-2 text-xs text-ls-muted">{{ emptyText }}</div>
      <button v-for="opt in options" :key="opt.value" type="button"
        @click="toggleValue(opt.value)"
        class="w-full text-left px-3 py-2 text-sm transition-colors flex items-center gap-2"
        :class="isSelected(opt.value) ? 'bg-ls-accent/10 text-ls-accent' : 'text-ls-text hover:bg-ls-elevated'">
        <span class="w-4 h-4 rounded border flex items-center justify-center flex-shrink-0"
          :class="isSelected(opt.value) ? 'bg-ls-accent border-ls-accent' : 'border-gray-600'">
          <CIcon v-if="isSelected(opt.value)" name="check" :size="10" :stroke-width="3" />
        </span>
        <span class="truncate">{{ opt.label }}</span>
        <span v-if="opt.extra" class="text-ls-muted text-[10px] ml-auto flex-shrink-0">{{ opt.extra }}</span>
      </button>
    </div>
  </div>
</template>
