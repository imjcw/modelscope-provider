<template>
  <div class="flex h-screen overflow-hidden">
    <Sidebar class="hidden lg:flex" />
    <main class="flex-1 ml-0 lg:ml-60 bg-ls-bg min-h-screen min-w-0 overflow-y-auto">
      <router-view />
    </main>
    <Toast v-model:visible="toastVisible" :message="toastMessage" :type="toastType" />
  </div>
  <SidebarDrawer v-model="sidebarOpen" />
</template>

<script setup>
import { ref, inject, provide } from 'vue'
import Sidebar from '@/components/Sidebar.vue'
import SidebarDrawer from '@/components/SidebarDrawer.vue'
import Toast from '@/components/Toast.vue'

const sidebarOpen = ref(false)
provide('sidebarOpen', sidebarOpen)

const toastVisible = inject('toastVisible')
const toastMessage = inject('toastMessage')
const toastType = inject('toastType')
</script>
