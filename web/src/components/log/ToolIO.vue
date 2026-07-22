<script setup>
/**
 * ToolIO — 工具调用的「入参 / 出参」标签块，支持 MD / RAW 两种渲染。
 */
import MarkdownRender from '@/components/MarkdownRender.vue'

defineProps({
  label: { type: String, required: true },        // 入参 | 出参
  tone: { type: String, default: 'in' },          // in = 蓝 | out = 紫
  source: { type: String, default: '' },
  raw: { type: Boolean, default: false },
})
</script>

<template>
  <div>
    <div class="flex items-center gap-2 mb-1">
      <span class="inline-flex items-center rounded-md px-1.5 py-0.5 text-xs"
        :class="tone === 'out' ? 'bg-purple-500/10 text-purple-400' : 'bg-blue-500/10 text-blue-400'">
        {{ label }}
      </span>
    </div>
    <div class="bg-ls-bg rounded-lg border border-ls-border p-3">
      <MarkdownRender v-if="!raw" :source="source" />
      <pre v-else class="text-xs text-gray-300 font-mono whitespace-pre-wrap overflow-x-auto">{{ source }}</pre>
    </div>
  </div>
</template>
