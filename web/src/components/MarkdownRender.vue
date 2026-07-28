<script setup>
/**
 * MarkdownRender — 渲染 markdown 内容。
 * 代码块通过事件委托实现复制，避免 inline onclick 的转义问题。
 */
import { computed, onMounted, onBeforeUnmount, ref, inject } from 'vue'
import MarkdownIt from 'markdown-it'

const props = defineProps({
  source: { type: String, required: true },
})

const emit = defineEmits(['frontmatter'])

const containerRef = ref(null)
const toast = inject('$toast', null)

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
})

// Plugin: fenced code blocks with base64 data-code for copy handler
md.use(function codeBlockPlugin(md) {
  md.renderer.rules.fence = function(tokens, idx) {
    const token = tokens[idx]
    const lang = token.info ? token.info.trim() : ''
    const content = token.content

    const dataCode = btoa(unescape(encodeURIComponent(content)))
    const rawLines = content.endsWith('\n') ? content.slice(0, -1).split('\n') : content.split('\n')

    let bodyHtml = ''
    for (let i = 0; i < rawLines.length; i++) {
      const num = String(i + 1).padStart(2, ' ')
      const text = md.utils.escapeHtml(rawLines[i])
      bodyHtml += '<div style="display:flex">' +
        '<span class="cb-num" style="color:var(--code-num)">' + num + '</span>' +
        '<span class="cb-text" style="color:var(--code-text)">' + text + '</span>' +
        '</div>'
    }

    const langHtml = lang
      ? '<span class="cb-lang"><span class="cb-dot"></span>' + md.utils.escapeHtml(lang) + '</span>'
      : '<span class="cb-lang"><span class="cb-dot"></span>&nbsp;</span>'

    return '<div class="codeblock" data-code="' + dataCode + '">' +
      '<div class="cb-header">' + langHtml +
      '<button class="cb-copy" type="button" title="复制">' +
      '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">' +
      '<rect x="9" y="9" width="13" height="13" rx="2"/>' +
      '<path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg></button></div>' +
      '<div class="cb-body">' + bodyHtml + '</div></div>\n'
  }
})

const YAML_FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/

function stripLineNumbers(src) {
  const lines = src.split('\n')
  if (lines.length < 2) return src
  const LINE_NUM_RE = /^\s*(\d+)\s+(.*)$/
  let matched = 0
  for (const line of lines) {
    if (LINE_NUM_RE.test(line)) matched++
  }
  if (matched / lines.length > 0.5) {
    return lines.map(line => {
      const m = line.match(LINE_NUM_RE)
      return m ? m[2] : line
    }).join('\n')
  }
  return src
}

function parseSource(src) {
  const cleaned = stripLineNumbers(src)
  // Strip internal framework injection tags that should never render
  const stripped = cleaned.replace(/<\?system-reminder[\s\S]*?<\/system-reminder\?>/gi, '')
  const match = stripped.match(YAML_FRONTMATTER_RE)
  if (match) {
    emit('frontmatter', match[1])
    return match[2]
  }
  return stripped
}

const html = computed(() => {
  const body = parseSource(props.source)
  return md.render(body)
})

function handleCopyClick(e) {
  const btn = e.target.closest('.cb-copy')
  if (!btn) return
  e.preventDefault()
  const block = btn.closest('.codeblock')
  if (!block) return
  const code = decodeURIComponent(escape(atob(block.dataset.code || '')))
  navigator.clipboard.writeText(code).then(() => {
    toast?.('已复制到剪贴板', 'success')
  }).catch(() => {
    toast?.('复制失败', 'error')
  })
}

onMounted(() => {
  containerRef.value?.addEventListener('click', handleCopyClick)
})
onBeforeUnmount(() => {
  containerRef.value?.removeEventListener('click', handleCopyClick)
})
</script>

<template>
  <div ref="containerRef" class="md-content">
    <div v-html="html"></div>
  </div>
</template>

<style scoped>
.md-content {
  color: var(--text);
  font-size: 13px;
  line-height: 1.7;
}

.md-content :deep(p) { margin: 0 0 0.8em; }
.md-content :deep(p:last-child) { margin-bottom: 0; }

.md-content :deep(h1), .md-content :deep(h2), .md-content :deep(h3),
.md-content :deep(h4), .md-content :deep(h5), .md-content :deep(h6) {
  margin: 1em 0 0.5em;
  font-weight: 600;
  line-height: 1.35;
  color: var(--text);
}
.md-content :deep(h1) { font-size: 1.3em; }
.md-content :deep(h2) { font-size: 1.15em; }
.md-content :deep(h3) { font-size: 1.05em; }
.md-content :deep(h4) { font-size: 1em; }

.md-content :deep(ul), .md-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.6em;
}
.md-content :deep(li) { margin: 0.2em 0; }
.md-content :deep(li p) { margin: 0.15em 0; }
.md-content :deep(li > ul), .md-content :deep(li > ol) { margin: 0.2em 0; }

.md-content :deep(a) {
  color: var(--accent);
  text-decoration: none;
}
.md-content :deep(a:hover) { text-decoration: underline; }

.md-content :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.3em 0.8em;
  border-left: 3px solid var(--accent);
  color: var(--text-dim);
  background: rgba(137, 180, 250, 0.04);
  border-radius: 0 6px 6px 0;
}
.md-content :deep(blockquote p:last-child) { margin-bottom: 0; }

.md-content :deep(hr) {
  margin: 1.2em 0;
  border: none;
  border-top: 1px solid var(--border);
}

.md-content :deep(table) {
  border-collapse: collapse;
  margin: 0.6em 0;
  width: 100%;
  font-size: 12px;
}
/* 表头：仅底边线（对齐 ApiKeys 对接指南的错误码表风格） */
.md-content :deep(thead th) {
  border: none;
  border-bottom: 1px solid var(--border);
  padding: 0.5em 0.8em;
  text-align: left;
  font-weight: 600;
  color: var(--text-muted);
  background: transparent;
}
/* 单元格：无边框、靠行分隔线区分（divide-y divide-ls-border） */
.md-content :deep(tbody td) {
  border: none;
  padding: 0.5em 0.8em;
  text-align: left;
  vertical-align: top;
  color: var(--text-dim);
}
.md-content :deep(tbody tr + tr) {
  border-top: 1px solid var(--border);
}

.md-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border);
}

.md-content :deep(code) {
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.85em;
  padding: 0.15em 0.4em;
  border-radius: 5px;
  color: var(--text);
  border: 1px solid var(--border);
}

/* Fenced code blocks */
.md-content :deep(.codeblock) {
  margin: 0.8em 0;
  border-radius: 0.5rem;
  border: 1px solid var(--code-border);
  overflow: hidden;
  background: transparent;
}

.md-content :deep(.cb-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 32px;
  padding: 0 12px;
  border-bottom: 1px solid var(--code-sep);
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
}

.md-content :deep(.cb-lang) {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 10px;
  color: var(--code-muted);
}

.md-content :deep(.cb-dot) {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--chart-blue);
}

.md-content :deep(.cb-copy) {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px;
  border-radius: 3px;
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.6;
  transition: opacity 0.15s;
}
.md-content :deep(.cb-copy:hover) {
  opacity: 1;
  color: var(--text);
}

.md-content :deep(.cb-body) {
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 12px;
  overflow-x: auto;
  padding: 8px 0;
}

.md-content :deep(.cb-body > div) { display: flex; }

.md-content :deep(.cb-num) {
  width: 36px;
  flex-shrink: 0;
  text-align: right;
  padding-right: 8px;
  user-select: none;
  line-height: 20px;
  font-variant-numeric: tabular-nums;
  border-right: 1px solid var(--code-sep);
  margin: -8px 0;
  padding-top: 8px;
  padding-bottom: 8px;
}

.md-content :deep(.cb-text) {
  flex: 1;
  line-height: 20px;
  white-space: pre-wrap;
  padding-left: 12px;
}
</style>
