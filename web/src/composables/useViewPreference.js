import { ref, watch } from 'vue'

/**
 * Persist a view preference to localStorage and restore it on refresh.
 * Lightweight wrapper — no external deps, matches this app's Vue 3 + Vite style.
 */
export function useViewPreference(key, defaultValue) {
  const stored = localStorage.getItem(key)
  const value = ref(stored !== null ? stored : defaultValue)
  watch(value, (v) => localStorage.setItem(key, v))
  return value
}
