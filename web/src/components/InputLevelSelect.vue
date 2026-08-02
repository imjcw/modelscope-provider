<script setup>
import { computed } from 'vue'

const props = defineProps({
  suppliers: { type: Array, required: true },
  modelsBySupplier: { type: Object, required: true },
  supplierId: { type: String, default: '' },
  model: { type: String, default: '' },
})

const selectedSupplier = computed(() =>
  props.suppliers.find(s => s.value === props.supplierId) || null,
)
const selectedModel = computed(() => {
  const opts = props.modelsBySupplier[props.supplierId] || []
  return opts.find(o => o.value === props.model) || null
})
const cleanLabel = (s) => s.replace(/（智能路由）$/, '').replace(/\(Smart Routing\)$/, '')
const label = computed(() =>
  selectedSupplier.value && selectedModel.value
    ? selectedSupplier.value.label + ' / ' + cleanLabel(selectedModel.value.label)
    : '',
)
</script>

<template>
  <span v-if="label"
    class="h-8 px-2 flex items-center gap-1.5 text-xs text-ls-muted font-mono"
    :title="label">
    <span class="truncate">{{ label }}</span>
  </span>
</template>
