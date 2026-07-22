<template>
  <nav class="flex-1 px-2 mt-2 space-y-0.5">
    <!-- Overview：监控与使用（cyan hover） -->
    <p class="px-3 mb-2 text-[10px] font-medium text-ls-muted uppercase tracking-[0.15em]">Overview</p>
    <router-link to="/" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
        <rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/>
      </svg>
      仪表盘
    </router-link>
    <router-link to="/mappings" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10 13a5 5 0 0 0 7.54 .54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
      虚拟模型
    </router-link>
    <router-link to="/logs" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
      请求日志
    </router-link>
    <router-link to="/alerts" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
        <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
      </svg>
      告警历史
    </router-link>
    <router-link to="/test" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="5 3 19 12 5 21 5 3"/>
      </svg>
      在线测试
    </router-link>
    <router-link to="/guide" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14"/>
        <path d="M9 12h6"/><path d="M9 16h4"/>
      </svg>
      使用指南
    </router-link>

    <!-- System：管理类（供应商/配置用 fuchsia hover，对应 demo 的 Members/Settings） -->
    <p class="px-3 mt-6 mb-2 text-[10px] font-medium text-ls-muted uppercase tracking-[0.15em]">System</p>
    <router-link to="/suppliers" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/>
        <path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/>
      </svg>
      供应商管理
    </router-link>
    <router-link to="/keys" class="nav-item" @click="$emit('select')">
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
  @apply flex items-center gap-3 px-3 py-2 rounded-lg text-ls-dim text-sm font-medium transition-colors;
}
.nav-item:hover {
  @apply text-ls-accent bg-ls-accent/5;
}
/* System 组管理项：fuchsia hover（demo 的 Members/Settings 配色） */
.nav-item-fuchsia:hover {
  @apply text-ls-fuchsia bg-ls-fuchsia/5;
}
.router-link-active {
  @apply bg-ls-accent/10 text-ls-accent;
}
</style>
