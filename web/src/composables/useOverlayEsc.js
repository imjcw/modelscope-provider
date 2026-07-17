/**
 * Centralized overlay key handler — ESC closes topmost, Enter confirms topmost.
 *
 * Usage:
 *   const { register, unregister } = useOverlayEsc()
 *   const id = register({ close: () => {}, confirm: () => {} })
 *   unregister(id)
 */

const stack = []
let bound = null

function handleKey(e) {
  if (stack.length === 0) return

  const top = stack[stack.length - 1]

  if (e.key === 'Escape') {
    top.close()
    stack.pop()
  } else if (e.key === 'Enter') {
    // Only handle Enter if the topmost overlay has a confirm handler
    if (top.confirm) {
      e.preventDefault()
      top.confirm()
    }
  }
}

export function useOverlayEsc() {
  function register(handlers) {
    if (!bound) {
      bound = handleKey
      document.addEventListener('keydown', bound)
    }
    const id = Date.now() + '-' + Math.random().toString(36).slice(2, 6)
    stack.push({ id, close: handlers.close, confirm: handlers.confirm || null })
    return id
  }

  function unregister(id) {
    const idx = stack.findIndex(h => h.id === id)
    if (idx !== -1) stack.splice(idx, 1)
    if (stack.length === 0 && bound) {
      document.removeEventListener('keydown', bound)
      bound = null
    }
  }

  return { register, unregister }
}
