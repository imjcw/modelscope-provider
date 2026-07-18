<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
// highlight.js core + commonly-used languages (full bundle is 1MB+)
import hljs from 'highlight.js/lib/core'
import js from 'highlight.js/lib/languages/javascript'
import ts from 'highlight.js/lib/languages/typescript'
import python from 'highlight.js/lib/languages/python'
import json from 'highlight.js/lib/languages/json'
import yaml from 'highlight.js/lib/languages/yaml'
import bash from 'highlight.js/lib/languages/bash'
import shell from 'highlight.js/lib/languages/shell'
import css from 'highlight.js/lib/languages/css'
import xmlLang from 'highlight.js/lib/languages/xml'
import markdown from 'highlight.js/lib/languages/markdown'
import http from 'highlight.js/lib/languages/http'
import diff from 'highlight.js/lib/languages/diff'
import sql from 'highlight.js/lib/languages/sql'
import dockerfile from 'highlight.js/lib/languages/dockerfile'
import go from 'highlight.js/lib/languages/go'
import rust from 'highlight.js/lib/languages/rust'
import java from 'highlight.js/lib/languages/java'
import php from 'highlight.js/lib/languages/php'
import ruby from 'highlight.js/lib/languages/ruby'
import kotlin from 'highlight.js/lib/languages/kotlin'
import plaintext from 'highlight.js/lib/languages/plaintext'

hljs.registerLanguage('javascript', js)
hljs.registerLanguage('js', js)
hljs.registerLanguage('typescript', ts)
hljs.registerLanguage('ts', ts)
hljs.registerLanguage('python', python)
hljs.registerLanguage('py', python)
hljs.registerLanguage('json', json)
hljs.registerLanguage('yaml', yaml)
hljs.registerLanguage('yml', yaml)
hljs.registerLanguage('bash', bash)
hljs.registerLanguage('shell', shell)
hljs.registerLanguage('sh', shell)
hljs.registerLanguage('css', css)
hljs.registerLanguage('xml', xmlLang)
hljs.registerLanguage('html', xmlLang)
hljs.registerLanguage('markdown', markdown)
hljs.registerLanguage('md', markdown)
hljs.registerLanguage('http', http)
hljs.registerLanguage('diff', diff)
hljs.registerLanguage('sql', sql)
hljs.registerLanguage('dockerfile', dockerfile)
hljs.registerLanguage('go', go)
hljs.registerLanguage('rust', rust)
hljs.registerLanguage('rs', rust)
hljs.registerLanguage('java', java)
hljs.registerLanguage('php', php)
hljs.registerLanguage('ruby', ruby)
hljs.registerLanguage('rb', ruby)
hljs.registerLanguage('kotlin', kotlin)
hljs.registerLanguage('kt', kotlin)
hljs.registerLanguage('plaintext', plaintext)
hljs.registerLanguage('text', plaintext)

const props = defineProps({
  source: { type: String, required: true },
})

const emit = defineEmits(['frontmatter'])

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true,
  // Built-in highlight option: wraps fenced code with hljs
  hljs,
})

// Plugin: wrap fenced code blocks in a styled container with header + line numbers
md.use(function codeBlockPlugin(md) {
  const fenceRender = md.renderer.rules.fence || function(tokens, idx) {
    return '<pre><code>' + md.utils.escapeHtml(tokens[idx].content) + '</code></pre>\n'
  }

  md.renderer.rules.fence = function(tokens, idx) {
    const token = tokens[idx]
    const lang = token.info ? token.info.trim() : ''
    const content = token.content

    // Count logical lines (strip trailing newline)
    const rawLines = content.endsWith('\n') ? content.slice(0, -1).split('\n') : content.split('\n')
    const lineCount = rawLines.length || 1

    // Build line number column
    let lineNums = ''
    for (let i = 1; i <= lineCount; i++) {
      lineNums += '<span>' + i + '</span>'
    }

    // Header: language with dot, copy button
    const langHtml = lang
      ? '<span class="cb-lang"><span class="cb-dot"></span>' + md.utils.escapeHtml(lang) + '</span>'
      : '<span class="cb-lang"><span class="cb-dot"></span></span>'

    // The inner <pre><code> rendered by markdown-it hljs (syntax-highlighted)
    const inner = fenceRender(tokens, idx)

    return '<div class="codeblock">' +
      '<div class="cb-header">' + langHtml +
      '<button class="cb-copy" type="button" title="Copy" onclick="navigator.clipboard.writeText(this.closest(\'.codeblock\').querySelector(\'.cb-code pre code\').innerText)">&#x1F4CB;</button></div>' +
      '<div class="cb-body">' +
      '<div class="cb-linenumbers">' + lineNums + '</div>' +
      '<div class="cb-code">' + inner + '</div>' +
      '</div></div>\n'
  }
})

// Extract YAML frontmatter: ---\n...\n--- at the very start
const YAML_FRONTMATTER_RE = /^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$/

// Strip line number prefixes like "1 ---\n2 name: ..." that some tools embed
function stripLineNumbers(src) {
  const lines = src.split('\n')
  if (lines.length < 2) return src

  // Heuristic: if every line starts with "N " (optional spaces, then digits, then space), strip it
  const LINE_NUM_RE = /^\s*(\d+)\s+(.*)$/
  let matched = 0
  for (const line of lines) {
    if (LINE_NUM_RE.test(line)) matched++
  }

  // Require >50% of lines to match the pattern to avoid false positives
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
  const match = cleaned.match(YAML_FRONTMATTER_RE)
  if (match) {
    emit('frontmatter', match[1])
    return match[2]
  }
  return cleaned
}

const html = computed(() => {
  const body = parseSource(props.source)
  return md.render(body)
})
</script>

<template>
  <div class="md-content">
    <div v-html="html"></div>
  </div>
</template>

<style scoped>
/* ── Prose base ── */
.md-content {
  color: var(--text);
  font-size: 13px;
  line-height: 1.7;
}

.md-content :deep(p) {
  margin: 0 0 0.8em;
}
.md-content :deep(p:last-child) {
  margin-bottom: 0;
}

/* ── Headings ── */
.md-content :deep(h1), .md-content :deep(h2), .md-content :deep(h3),
.md-content :deep(h4), .md-content :deep(h5), .md-content :deep(h6) {
  margin: 1em 0 0.5em;
  font-weight: 600;
  line-height: 1.35;
  color: #fff;
}
.md-content :deep(h1) { font-size: 1.3em; }
.md-content :deep(h2) { font-size: 1.15em; }
.md-content :deep(h3) { font-size: 1.05em; }
.md-content :deep(h4) { font-size: 1em; }

/* ── Lists ── */
.md-content :deep(ul), .md-content :deep(ol) {
  margin: 0.5em 0;
  padding-left: 1.6em;
}
.md-content :deep(li) {
  margin: 0.2em 0;
}
.md-content :deep(li p) {
  margin: 0.15em 0;
}
.md-content :deep(li > ul), .md-content :deep(li > ol) {
  margin: 0.2em 0;
}

/* ── Links ── */
.md-content :deep(a) {
  color: var(--accent);
  text-decoration: none;
}
.md-content :deep(a:hover) {
  text-decoration: underline;
}

/* ── Blockquote ── */
.md-content :deep(blockquote) {
  margin: 0.6em 0;
  padding: 0.3em 0.8em;
  border-left: 3px solid var(--accent);
  color: var(--text-dim);
  background: rgba(137, 180, 250, 0.04);
  border-radius: 0 6px 6px 0;
}
.md-content :deep(blockquote p:last-child) {
  margin-bottom: 0;
}

/* ── Horizontal rule ── */
.md-content :deep(hr) {
  margin: 1.2em 0;
  border: none;
  border-top: 1px solid var(--border);
}

/* ── Tables ── */
.md-content :deep(table) {
  border-collapse: collapse;
  margin: 0.6em 0;
  width: 100%;
  font-size: 12px;
}
.md-content :deep(th), .md-content :deep(td) {
  padding: 0.45em 0.7em;
  border: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}
.md-content :deep(th) {
  background: var(--surface-2);
  font-weight: 600;
  color: #fff;
}
.md-content :deep(tr:nth-child(even) td) {
  background: rgba(255, 255, 255, 0.015);
}

/* ── Images ── */
.md-content :deep(img) {
  max-width: 100%;
  border-radius: 8px;
  border: 1px solid var(--border);
}

/* ── Inline code ── */
.md-content :deep(code) {
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.85em;
  padding: 0.15em 0.4em;
  border-radius: 5px;
  background: var(--surface-2);
  color: #f2cdcd;
  border: 1px solid var(--border);
}

/* ── Fenced code blocks (custom plugin output) ── */
.md-content :deep(.codeblock) {
  margin: 0.8em 0;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: #0f0f10;
  overflow: hidden;
}

.md-content :deep(.cb-header) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 12px;
  background: var(--surface-2);
  border-bottom: 1px solid var(--border);
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 11px;
  color: var(--text-muted);
}

.md-content :deep(.cb-lang) {
  display: flex;
  align-items: center;
  gap: 6px;
}

.md-content :deep(.cb-dot) {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent);
}

.md-content :deep(.cb-copy) {
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 13px;
  opacity: 0.5;
  transition: opacity 0.15s;
}
.md-content :deep(.cb-copy:hover) {
  opacity: 1;
  background: rgba(255, 255, 255, 0.06);
}

.md-content :deep(.cb-body) {
  display: flex;
  overflow-x: auto;
}

.md-content :deep(.cb-linenumbers) {
  padding: 12px 0;
  line-height: 1.6;
  color: #4a4a5a;
  font-size: 12px;
  text-align: right;
  user-select: none;
  flex-shrink: 0;
}
.md-content :deep(.cb-linenumbers span) {
  display: block;
  padding-right: 12px;
  min-width: 24px;
}

.md-content :deep(.cb-code) {
  flex: 1;
  min-width: 0;
}

.md-content :deep(.cb-code pre) {
  margin: 0;
  padding: 12px 16px 12px 12px;
  overflow: visible;
}

.md-content :deep(.cb-code pre code) {
  display: block;
  padding: 0;
  font-size: 12px;
  line-height: 1.6;
  font-family: ui-monospace, 'SF Mono', 'Cascadia Code', 'Consolas', monospace;
  background: transparent !important;
  white-space: pre;
}

.md-content :deep(.cb-code pre code.hljs) {
  color: #cdd6f4;
}
</style>
