/**
 * Centralized ESC handler — closes only the topmost overlay.
 *
 * Usage in a component:
 *   const { register, unregister } = useOverlayEsc()
 *   // when opening:
 *   const id = register(closeFn)   // closeFn() is called on ESC
 *   // when closing (normally or by ESC):
 *   unregister(id)
 */

const stack = []
let bound = null

function handleEsc(e) {
  if (e.key !== 'Escape') return
  if (stack.length === 0) return
  // Pop and call the topmost handler
  const id = stack[stack.length - 1]
  const handler = stack.find(h => h.id === id)
  if (handler) {
    handler.close()
    // Remove from stack after calling
    const idx = stack.indexOf(handler)
    stack.splice(idx, 1)
  }
}

export function useOverlayEsc() {
  function register(closeFn) {
    // Ensure global listener is installed
    if (!bound) {
      bound = handleEsc
      document.addEventListener('keydown', bound)
    }
    const id = Date.now() + '-' + Math.random().toString(36).slice(2, 6)
    stack.push({ id, close: closeFn })
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
