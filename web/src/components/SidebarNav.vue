<template>
  <nav class="flex-1 px-2 mt-2">
    <!-- Overview：监控与使用（cyan hover） -->
    <p class="px-3 mt-4 mb-2 text-[10px] font-medium text-ls-muted uppercase tracking-[0.15em]">Overview</p>
    <router-link to="/" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        <polyline points="6 13 9.5 9.5 13 11.5 17.5 7.5"/>
      </svg>
      用量分析
    </router-link>
    <router-link to="/logs" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
      请求日志
    </router-link>
    <router-link to="/test" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      临时会话
    </router-link>
    <router-link to="/guide" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
      </svg>
      使用指南
    </router-link>

    <!-- System：管理类（供应商/配置用 fuchsia hover，对应 demo 的 Members/Settings） -->
    <p class="px-3 mt-4 mb-2 text-[10px] font-medium text-ls-muted uppercase tracking-[0.15em]">System</p>
    <router-link to="/suppliers" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
      供应商管理
    </router-link>
    <router-link to="/provider-types" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="12 2 2 7 12 12 22 7 12 2"/>
        <polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
      </svg>
      供应商类型
    </router-link>
    <router-link to="/mappings" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      智能路由
    </router-link>
    <router-link to="/keys" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="8" cy="15" r="5"/><path d="M11.5 11.5L21 2"/><path d="M16 7l3 3"/>
      </svg>
      API Keys
    </router-link>
    <router-link to="/config" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06"/>
      </svg>
      系统配置
    </router-link>
  </nav>
</template>

<script setup>
defineEmits(['select'])
</script>

<style scoped>
.nav-item {
  @apply flex items-center gap-3 px-3 py-2 rounded-lg text-ls-dim text-sm font-medium transition-colors mb-1;
}
.nav-item:hover {
  @apply text-ls-accent bg-ls-accent/5;
}
/* System 组管理项：fuchsia hover（demo 的 Members/Settings 配色） */
.nav-item-fuchsia:hover {
  @apply text-ls-fuchsia bg-ls-fuchsia/5;
}
.router-link-active {
  @apply bg-ls-accent/15 text-ls-accent;
}
</style>
