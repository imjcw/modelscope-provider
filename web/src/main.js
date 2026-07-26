import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './assets/main.css'

// 同步应用初始主题，避免闪屏
(function initTheme() {
  const saved = localStorage.getItem('themeMode')
  if (!saved) return
  let brightness = 'dark'
  if (saved === 'light') {
    brightness = 'light'
  } else if (saved === 'system') {
    brightness = window.matchMedia &&
      window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
  }
  document.documentElement.setAttribute('data-theme', brightness)
})()

// ── Router ──
const routes = [
  { path: '/', name: 'dashboard', component: () => import('./pages/Dashboard.vue') },
  { path: '/suppliers', name: 'suppliers', component: () => import('./pages/Accounts.vue') },
  { path: '/provider-types', name: 'provider-types', component: () => import('./pages/ProviderTypes.vue') },
  { path: '/mappings', name: 'mappings', component: () => import('./pages/Mappings.vue') },
  { path: '/logs', name: 'logs', component: () => import('./pages/Logs.vue') },
  { path: '/alerts', name: 'alerts', component: () => import('./pages/Alerts.vue') },
  { path: '/test', name: 'test', component: () => import('./pages/Test.vue') },
  { path: '/config', name: 'config', component: () => import('./pages/Config.vue') },
  { path: '/guide', name: 'guide', component: () => import('./pages/Guide.vue') },
  { path: '/keys', name: 'keys', component: () => import('./pages/ApiKeys.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

import { ref } from 'vue'

const app = createApp(App)

const toastVisible = ref(false)
const toastMessage = ref('')
const toastType = ref('info')

const toast = (message, type = 'info') => {
  toastMessage.value = message
  toastType.value = type
  toastVisible.value = true
}

app.provide('toastVisible', toastVisible)
app.provide('toastMessage', toastMessage)
app.provide('toastType', toastType)
app.provide('$toast', toast)
app.use(router).mount('#app')
