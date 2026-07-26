<script setup>
/**
 * CodeBlock — 带行号的代码展示框。
 * 无背景色、等宽纯文本、行号独立列、右侧 border、顶部标题栏 + 复制按钮。
 *
 * Props:
 *   code      代码文本（多行字符串）
 *   lang      语言标识（显示在标题栏，如 'bash' / 'python'）
 *
 * Usage:
 *   <CodeBlock lang="bash" :code="snippet" />
 */
import { computed } from 'vue'
import CopyButton from './CopyButton.vue'

const props = defineProps({
  code: { type: String, default: '' },
  lang: { type: String, default: '' },
})

const lines = computed(() => {
  const c = props.code.trimEnd()
  return c ? c.split('\n') : []
})
</script>

<template>
  <div class="rounded-lg border border-[var(--code-border)] overflow-hidden">
    <!-- Header -->
    <div class="flex items-center justify-between h-8 px-3 border-b border-[var(--code-sep)]">
      <span v-if="lang" class="text-[10px] font-mono flex items-center gap-1.5" style="color: var(--code-muted)">
        <span class="w-1.5 h-1.5 rounded-full bg-blue-500"></span>{{ lang }}
      </span>
      <span v-else class="text-[10px] font-mono flex items-center gap-1.5" style="color: var(--code-muted)">&nbsp;</span>
      <CopyButton :text="code" :size="12" />
    </div>
    <!-- Body -->
    <div class="block font-mono text-xs overflow-x-auto py-2">
      <div v-for="(line, i) in lines" :key="i" style="display: flex">
        <span class="w-[36px] flex-shrink-0 text-right pr-2 select-none leading-5 tabular-nums border-r border-[var(--code-sep)] -my-2 py-2" style="color: var(--code-num)">{{ String(i + 1).padStart(2, ' ') }}</span>
        <span class="flex-1 leading-5 whitespace-pre-wrap pl-3" style="color: var(--code-text)">{{ line }}</span>
      </div>
    </div>
  </div>
</template>
