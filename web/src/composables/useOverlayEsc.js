/**
 * Centralized overlay key handler — ESC closes the topmost (highest z-index) overlay.
 *
 * Instead of relying on a manual stack (which can get out of sync),
 * this queries the DOM for all overlay root elements and closes the one
 * with the highest CSS z-index.
 */

function getOverlayZIndex(el) {
  // Walk up from the element to find the one that's position: fixed (overlay root)
  let current = el
  while (current && current !== document.body) {
    const style = window.getComputedStyle(current)
    if (style.position === 'fixed' && style.zIndex !== 'auto') {
      return parseInt(style.zIndex, 10) || 0
    }
    current = current.parentElement
  }
  return 0
}

function handleKey(e) {
  if (e.key !== 'Escape' && e.key !== 'Enter') return

  // Collect all overlay roots that are visible
  const drawers = [...document.querySelectorAll('.drawer-overlay')]
  const modals = [...document.querySelectorAll('.modal-overlay')]
  const overlays = [...drawers, ...modals]

  if (overlays.length === 0) return

  // Find the overlay with the highest z-index
  const top = overlays.reduce((best, el) => {
    const z = getOverlayZIndex(el)
    return z > best.z ? { el, z } : best
  }, { el: null, z: -Infinity })

  if (!top.el) return

  if (e.key === 'Escape') {
    // Find the component ref on the overlay's parent or via a close button
    // For Drawer: trigger the close button
    // For ConfirmModal: trigger the close button
    const closeBtn = top.el.querySelector('.drawer-close, .modal-actions .btn-secondary')
    if (closeBtn) {
      closeBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }))
    }
  } else if (e.key === 'Enter') {
    // Only confirm on ConfirmModal (has modal-actions with primary/danger button)
    if (top.el.classList.contains('modal-overlay')) {
      const confirmBtn = top.el.querySelector('.modal-actions .btn-primary, .modal-actions .btn-danger')
      if (confirmBtn && !confirmBtn.disabled) {
        confirmBtn.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      }
    }
  }
}

document.addEventListener('keydown', handleKey)
