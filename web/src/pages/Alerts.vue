<template>
  <div>
    <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">{{ title }}</h1>
        <p class="text-xs text-gray-500 mt-0.5">开发中</p>
      </div>
    </header>
    <div class="p-6">
      <p class="text-sm text-gray-500">页面开发中...</p>
    </div>
  </div>
</template>

<script setup>
const title = '告警历史'
</script>
