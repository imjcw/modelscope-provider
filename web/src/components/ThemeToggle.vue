<template>
  <div class="theme-toggle">
    <select
      class="theme-select"
      :value="getMode()"
      @change="handleChange"
    >
      <option value="light">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 4px;">
          <circle cx="12" cy="12" r="4"/>
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/>
        </svg>
        白天
      </option>
      <option value="dark">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 4px;">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
        夜间
      </option>
      <option value="system">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: -1px; margin-right: 4px;">
          <rect x="2" y="3" width="20" height="14" rx="2"/>
          <line x1="8" y1="21" x2="16" y2="21"/>
          <line x1="12" y1="17" x2="12" y2="21"/>
        </svg>
        系统
      </option>
    </select>
  </div>
</template>

<script setup>
import { useTheme } from '@/composables/useTheme.js'

const { currentMode, setMode } = useTheme()

const handleChange = (e) => {
  setMode(e.target.value)
}
</script>

<style scoped>
.theme-select {
  appearance: none;
  -webkit-appearance: none;
  -moz-appearance: none;
  background: var(--ls-card);
  border: 1px solid var(--ls-border);
  border-radius: 6px;
  padding: 4px 22px 4px 8px;
  font-size: 11px;
  color: var(--text-dim);
  cursor: pointer;
  transition: all .15s;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='10' height='10' viewBox='0 0 24 24' fill='none' stroke='%236b7280' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'%3E%3C/polyline%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 6px center;
}
.theme-select:hover {
  border-color: var(--ls-accent);
  color: var(--text);
}
.theme-select:focus {
  outline: none;
  border-color: var(--ls-accent);
  box-shadow: 0 0 0 2px var(--ring);
}
</style>
