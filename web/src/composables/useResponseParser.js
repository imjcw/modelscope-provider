/**
 * Shared response-stream parser for LogDetailPanel and other log viewers.
 *
 * Handles three formats found in raw_response:
 *   1. Single JSON object  (non-streamed / full response)
 *   2. SSE "data:" lines   (streamed)
 *   3. Raw JSON-lines      (brace-matching fallback)
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
  } catch {}

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
