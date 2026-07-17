<template>
  <div class="flex h-screen overflow-hidden">
    <!-- Sidebar -->
    <Sidebar />
    <!-- Main content -->
    <main class="flex-1 bg-ls-bg overflow-y-auto min-w-0">
      <router-view />
    </main>

    <Toast :visible="toastVisible" :message="toastMessage" :type="toastType" @update:visible="toastVisible = $event" />
  </div>
</template>

<script setup>
import Sidebar from './components/Sidebar.vue'
import Toast from './components/Toast.vue'
import { inject } from 'vue'
const toastVisible = inject('toastVisible')
const toastMessage = inject('toastMessage')
const toastType = inject('toastType')
</script>
