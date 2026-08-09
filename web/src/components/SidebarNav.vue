<template>
  <nav class="flex-1 px-2 mt-2">
    <!-- Overview：监控与使用（cyan hover） -->
    <p class="px-3 mt-4 mb-2 text-[10px] font-medium text-ls-muted uppercase tracking-[0.15em]">Overview</p>
    <router-link to="/web" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <rect x="2" y="3" width="20" height="14" rx="2"/>
        <line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
        <polyline points="6 13 9.5 9.5 13 11.5 17.5 7.5"/>
      </svg>
      用量分析
    </router-link>
    <router-link to="/web/logs" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <path d="M14 2v6h6"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
      </svg>
      请求日志
    </router-link>
    <router-link to="/web/test" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
      </svg>
      临时会话
    </router-link>
    <router-link to="/web/guide" class="nav-item" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <circle cx="12" cy="12" r="10"/>
        <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76"/>
      </svg>
      使用指南
    </router-link>

    <!-- System：管理类（供应商/配置用 fuchsia hover，对应 demo 的 Members/Settings） -->
    <p class="px-3 mt-4 mb-2 text-[10px] font-medium text-ls-muted uppercase tracking-[0.15em]">System</p>
    <router-link to="/web/suppliers" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M14 4a1 1 0 0 1 1 -1h5a1 1 0 0 1 1 1v5a1 1 0 0 1 -1 1h-5a1 1 0 0 1 -1 -1l0 -5"/>
        <path d="M3 14h12a2 2 0 0 1 2 2v3a2 2 0 0 1 -2 2h-10a2 2 0 0 1 -2 -2v-10a2 2 0 0 1 2 -2h3a2 2 0 0 1 2 2v12"/>
      </svg>
      供应商管理
    </router-link>
    <router-link to="/web/provider-types" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <polygon points="12 2 2 7 12 12 22 7 12 2"/>
        <polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/>
      </svg>
      供应商类型
    </router-link>
    <router-link to="/web/mappings" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M7.5 21 3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5"/>
      </svg>
      智能路由
    </router-link>
    <router-link to="/web/keys" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <circle cx="8" cy="15" r="5"/><path d="M11.5 11.5L21 2"/><path d="M16 7l3 3"/>
      </svg>
      API Keys
    </router-link>
    <router-link to="/web/config" class="nav-item nav-item-fuchsia" @click="$emit('select')">
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"
        stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M9.594 3.94c.09-.542.56-.94 1.11-.94h2.593c.55 0 1.02.398 1.11.94l.213 1.281c.063.374.313.686.645.87.074.04.147.083.22.127.325.196.72.257 1.075.124l1.217-.456a1.125 1.125 0 0 1 1.37.49l1.296 2.247a1.125 1.125 0 0 1-.26 1.431l-1.003.827c-.293.241-.438.613-.43.992a7.723 7.723 0 0 1 0 .255c-.008.378.137.75.43.991l1.004.827c.424.35.534.955.26 1.43l-1.298 2.247a1.125 1.125 0 0 1-1.369.491l-1.217-.456c-.355-.133-.75-.072-1.076.124a6.47 6.47 0 0 1-.22.128c-.331.183-.581.495-.644.869l-.213 1.281c-.09.543-.56.94-1.11.94h-2.594c-.55 0-1.019-.398-1.11-.94l-.213-1.281c-.062-.374-.312-.686-.644-.87a6.52 6.52 0 0 1-.22-.127c-.325-.196-.72-.257-1.076-.124l-1.217.456a1.125 1.125 0 0 1-1.369-.49l-1.297-2.247a1.125 1.125 0 0 1 .26-1.431l1.004-.827c.292-.24.437-.613.43-.991a6.932 6.932 0 0 1 0-.255c.007-.38-.138-.751-.43-.992l-1.004-.827a1.125 1.125 0 0 1-.26-1.43l1.297-2.247a1.125 1.125 0 0 1 1.37-.491l1.216.456c.356.133.751.072 1.076-.124.072-.044.146-.086.22-.128c.332-.183.582-.495.644-.869l.214-1.28Z"/>
        <path d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z"/>
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
