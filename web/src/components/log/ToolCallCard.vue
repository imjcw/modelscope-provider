<script setup>
/**
 * ToolCallCard — assistant 消息内联的工具调用卡（类型/名称/id + 入参 + 出参）。
 */
import ToolIO from './ToolIO.vue'
import { toolTypeClass, toolTypeLabel } from './toolType'

defineProps({
  tc: { type: Object, required: true }, // { name, id, arguments, result }
})
</script>

<template>
  <div class="bg-ls-bg rounded-lg border border-ls-border p-3">
    <div class="flex items-center gap-2 mb-2">
      <span :class="toolTypeClass(tc.name)" class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs">
        {{ toolTypeLabel(tc.name) }}
      </span>
      <span class="text-xs text-gray-400 font-medium">{{ tc.name }}</span>
      <span v-if="tc.id" class="text-xs text-gray-500 font-mono">{{ tc.id }}</span>
    </div>
    <div class="mb-2">
      <ToolIO label="入参" :source="tc.arguments" />
    </div>
    <div v-if="tc.result" class="mt-2 pt-2 border-t border-ls-border">
      <ToolIO label="出参" tone="out" :source="tc.result" />
    </div>
  </div>
</template>
