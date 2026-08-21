/**
 * Shared response-stream parser for LogDetailPanel and other log viewers.
 *
 * Handles the formats found in raw_response:
 *   1. Single JSON object   (OpenAI non-streamed / full response)
 *   2. SSE "data:" lines    (OpenAI streamed)
 *   3. Raw JSON-lines       (brace-matching fallback)
 *   4. Anthropic message    (Anthropic non-streamed: type=message, content blocks)
 *   5. Anthropic SSE events (Anthropic streamed: event:/data: with
 *      text_delta / thinking_delta / input_json_delta)
 *
 * Returns a normalized { choices: [...] } where each choice has:
 *   - message: { content, tool_calls, reasoning_content }
 *   - delta:   { content, tool_calls, reasoning_content }
 *
 * For streamed formats (SSE / JSON-lines), tool_calls are merged by index
 * so callers get a consolidated list rather than per-chunk fragments.
 *
 * Returns null if no format matched.
 */
export function parseResponseStreams(raw) {
  if (!raw) return null

  // ── Pass 1: single JSON object ──
  try {
    const parsed = JSON.parse(raw)
    const choices = parsed.choices || []
    if (choices.length > 0) {
      return { choices: choices.map(normalizeChoice) }
    }
    // Anthropic non-streamed message: content is an array of blocks
    // (text / thinking / tool_use). Normalize into the OpenAI-style shape.
    if (parsed.type === 'message' && Array.isArray(parsed.content)) {
      return { choices: [{ message: anthropicBlocksToMessage(parsed.content), delta: {} }] }
    }
  } catch {}

  // ── Pass 2.5: Anthropic SSE stream (event:/data: pairs) ──
  // Detection: contains "event:" blocks AND data payloads carrying
  // "type" of message_start / content_block_*. Must run before the OpenAI
  // "data:" check because Anthropic data: lines begin with {, not [DONE].
  if (raw.includes('\nevent:') || /^(event:)/m.test(raw)) {
    const anthropic = parseAnthropicSse(raw)
    if (anthropic) return anthropic
  }

  // ── Pass 2: SSE "data:" lines ──
  if (raw.startsWith('data:')) {
    const mergedToolCalls = {}
    const allChoices = []
    const lines = raw.split('\n')
    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const dataStr = line.slice(5).trim()
      if (dataStr === '[DONE]' || !dataStr) continue
      try {
        const obj = JSON.parse(dataStr)
        for (const c of obj.choices || []) {
          allChoices.push(c)
          const tc = (c.delta || {}).tool_calls
          if (Array.isArray(tc)) {
            for (const t of tc) {
              const idx = t.index ?? 0
              if (!mergedToolCalls[idx]) {
                mergedToolCalls[idx] = { id: '', type: 'function', name: '', arguments: '' }
              }
              if (t.id) mergedToolCalls[idx].id = t.id
              if (t.type) mergedToolCalls[idx].type = t.type
              if (t.function?.name) mergedToolCalls[idx].name = t.function.name
              if (t.function?.arguments) mergedToolCalls[idx].arguments += t.function.arguments
            }
          }
        }
      } catch {}
    }
    if (allChoices.length > 0 || Object.keys(mergedToolCalls).length > 0) {
      const choices = allChoices.map(normalizeChoice)
      // Attach merged tool_calls once at the top level so callers don't
      // duplicate them when iterating over choices.
      return {
        choices,
        _mergedToolCalls: Object.keys(mergedToolCalls).length > 0
          ? Object.values(mergedToolCalls)
          : undefined,
      }
    }
  }

  // ── Pass 3: raw JSON-lines with brace-matching ──
  try {
    const mergedToolCalls = {}
    const allChoices = []
    let pos = 0
    while (pos < raw.length) {
      let start = pos
      let depth = 0, inString = false, escape = false, end = start
      for (let i = start; i < raw.length; i++) {
        const ch = raw[i]
        if (inString) {
          if (escape) { escape = false }
          else if (ch === '\\') { escape = true }
          else if (ch === '"') { inString = false }
        } else {
          if (ch === '"') { inString = true }
          else if (ch === '{') { depth++ }
          else if (ch === '}') { depth-- }
          if (depth === 0 && !inString) { end = i + 1; break }
        }
      }
      if (end <= start) break
      const obj = JSON.parse(raw.slice(start, end))
      for (const c of obj.choices || []) {
        allChoices.push(c)
        const tc = (c.delta || {}).tool_calls
        if (Array.isArray(tc)) {
          for (const t of tc) {
            const idx = t.index ?? 0
            if (!mergedToolCalls[idx]) {
              mergedToolCalls[idx] = { id: '', type: 'function', name: '', arguments: '' }
            }
            if (t.id) mergedToolCalls[idx].id = t.id
            if (t.type) mergedToolCalls[idx].type = t.type
            if (t.function?.name) mergedToolCalls[idx].name = t.function.name
            if (t.function?.arguments) mergedToolCalls[idx].arguments += t.function.arguments
          }
        }
      }
      pos = end
    }
    if (allChoices.length > 0) {
      const choices = allChoices.map(normalizeChoice)
      return {
        choices,
        _mergedToolCalls: Object.keys(mergedToolCalls).length > 0
          ? Object.values(mergedToolCalls)
          : undefined,
      }
    }
  } catch {}

  return null
}

function normalizeChoice(choice) {
  const delta = choice.delta || {}
  const message = choice.message || {}

  // Sensenova / SenseNova streams reasoning in `delta.reasoning` (not
  // `reasoning_content`). Normalise it so callers only read one path.
  if (delta.reasoning) delta.reasoning_content = delta.reasoning
  if (message.reasoning) message.reasoning_content = message.reasoning

  return {
    message,
    delta,
  }
}

// ── Anthropic response normalization ──
// Anthropic content is an ordered list of blocks:
//   { type: 'text', text } | { type: 'thinking', thinking } |
//   { type: 'tool_use', id, name, input }
// Convert them into the OpenAI-style message consumed by LogDetailPanel.
function anthropicBlocksToMessage(blocks) {
  const content = []
  const reasoning = []
  const toolCalls = []
  for (const b of blocks || []) {
    if (!b || typeof b !== 'object') continue
    if (b.type === 'text' && b.text) content.push(b.text)
    else if (b.type === 'thinking' && b.thinking) reasoning.push(b.thinking)
    else if (b.type === 'tool_use') {
      let args = b.input ?? {}
      if (typeof args !== 'string') {
        try { args = JSON.stringify(args) } catch { args = '{}' }
      }
      toolCalls.push({
        id: b.id || '',
        type: 'function',
        function: { name: b.name || 'unknown', arguments: args },
      })
    }
  }
  return {
    role: 'assistant',
    content: content.join(''),
    reasoning_content: reasoning.join('\n'),
    tool_calls: toolCalls,
  }
}

// ── Anthropic SSE stream parser ──
// The provider proxies Anthropic's native event stream verbatim:
//   event: message_start / content_block_start / content_block_delta /
//          content_block_stop / message_delta / message_stop
//   data: { ... }
// Tool-use arguments arrive as fragmented input_json_delta.partial_json
// chunks that must be concatenated; thinking arrives as thinking_delta;
// regular text arrives as text_delta.
function parseAnthropicSse(raw) {
  // Block index → accumulated state
  const blocks = new Map() // index -> { type, text, thinking, tool: { id, name, args } }
  let sawContentBlock = false

  let curEvent = null
  for (const line of raw.split('\n')) {
    const trimmed = line.trim()
    if (trimmed.startsWith('event:')) {
      curEvent = trimmed.slice(6).trim()
      continue
    }
    if (!trimmed.startsWith('data:')) continue
    const dataStr = trimmed.slice(5).trim()
    if (!dataStr) continue
    let obj
    try { obj = JSON.parse(dataStr) } catch { continue }
    const type = obj.type || ''

    if (type === 'content_block_start') {
      const idx = obj.index ?? 0
      const cb = obj.content_block || {}
      let b = blocks.get(idx)
      if (!b) { b = { type: cb.type || 'text', text: '', thinking: '', tool: { id: '', name: '', args: '' } }; blocks.set(idx, b) }
      if (cb.type === 'tool_use') {
        b.type = 'tool_use'
        b.tool.id = cb.id || ''
        b.tool.name = cb.name || ''
        b.tool.args = ''
      }
      sawContentBlock = true
    } else if (type === 'content_block_delta') {
      const idx = obj.index ?? 0
      const delta = obj.delta || {}
      let b = blocks.get(idx)
      if (!b) { b = { type: 'text', text: '', thinking: '', tool: { id: '', name: '', args: '' } }; blocks.set(idx, b) }
      if (delta.type === 'text_delta') b.text += delta.text || ''
      else if (delta.type === 'thinking_delta') b.thinking += delta.thinking || ''
      else if (delta.type === 'input_json_delta') b.tool.args += delta.partial_json || ''
      sawContentBlock = true
    }
    // message_start / message_delta / content_block_stop / message_stop / ping
    // carry no displayable content — ignore.
  }

  if (!sawContentBlock) return null

  const message = anthropicBlocksToMessage(
    [...blocks.entries()]
      .sort((a, b) => a[0] - b[0])
      .map(([, b]) => {
        if (b.type === 'tool_use') {
          return { type: 'tool_use', id: b.tool.id, name: b.tool.name, input: b.tool.args }
        }
        if (b.type === 'thinking') return { type: 'thinking', thinking: b.thinking }
        return { type: 'text', text: b.text }
      })
  )
  if (!message.content && !message.reasoning_content && message.tool_calls.length === 0) {
    return null
  }
  // _mergedToolCalls uses flat format {id, type, name, arguments} to match
  // what the streamed branch of responseToolCalls expects (see LogDetailPanel).
  const merged = message.tool_calls.length > 0
    ? message.tool_calls.map(tc => ({
        id: tc.id || '',
        type: tc.type || 'function',
        name: tc.function?.name || 'unknown',
        arguments: tc.function?.arguments || '{}',
      }))
    : undefined
  return {
    choices: [{ message, delta: {} }],
    _mergedToolCalls: merged,
  }
}
