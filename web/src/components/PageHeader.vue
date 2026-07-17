<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
})
</script>

<template>
  <header class="bg-ls-bg/80 backdrop-blur-md border-b border-ls-border px-6 py-3 flex items-center justify-between sticky top-0 z-10">
    <div class="flex items-center gap-2">
      <slot name="title-prefix"></slot>
      <div>
        <h1 class="text-lg font-semibold tracking-tight text-white">{{ title }}</h1>
        <p v-if="subtitle" class="text-xs text-gray-500 mt-0.5">{{ subtitle }}</p>
      </div>
    </div>
    <div class="flex items-center gap-2.5">
      <slot name="action"></slot>
    </div>
  </header>
</template>
