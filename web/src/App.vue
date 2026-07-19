<template>
  <div class="flex h-screen overflow-hidden">
    <Sidebar class="hidden lg:flex" />
    <main class="flex-1 bg-ls-bg overflow-y-auto min-w-0">
      <router-view />
    </main>
    <Toast />
  </div>
  <SidebarDrawer v-model="sidebarOpen" />
</template>

<script setup>
import { ref, provide } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import SidebarDrawer from '@/components/SidebarDrawer.vue'
import Toast from '@/components/Toast.vue'

const sidebarOpen = ref(false)
provide('sidebarOpen', sidebarOpen)
</script>
