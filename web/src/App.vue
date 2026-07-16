<template>
  <div class="flex min-h-screen">
    <!-- Sidebar -->
    <Sidebar />
    <!-- Main content -->
    <main class="flex-1 bg-ls-bg overflow-auto">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
</script>
