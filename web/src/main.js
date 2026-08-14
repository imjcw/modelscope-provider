import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
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
  { path: '/web', name: 'dashboard', component: () => import('./pages/Dashboard.vue') },
  { path: '/web/suppliers', name: 'suppliers', component: () => import('./pages/Accounts.vue') },
  { path: '/web/provider-types', name: 'provider-types', component: () => import('./pages/ProviderTypes.vue') },
  { path: '/web/mappings', name: 'mappings', component: () => import('./pages/Mappings.vue') },
  { path: '/web/logs', name: 'logs', component: () => import('./pages/Logs.vue') },
  { path: '/web/alerts', name: 'alerts', component: () => import('./pages/Alerts.vue') },
  { path: '/web/test', name: 'test', component: () => import('./pages/Test.vue') },
  { path: '/web/config', name: 'config', component: () => import('./pages/Config.vue') },
  { path: '/web/guide', name: 'guide', component: () => import('./pages/Guide.vue') },
  { path: '/web/keys', name: 'keys', component: () => import('./pages/ApiKeys.vue') },
  { path: '/:pathMatch(.*)*', redirect: '/web' },
]

const router = createRouter({
  history: createWebHistory(),
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

// ── PWA Service Worker ──
if ('serviceWorker' in navigator) {
  const swUrl = '/web/sw.js'
  const registration = async () => {
    try {
      const reg = await navigator.serviceWorker.register(swUrl, { scope: '/web/' })
      // Auto-update when a new SW version is pushed
      reg.addEventListener('updatefound', () => {
        const newWorker = reg.installing
        newWorker.addEventListener('statechange', () => {
          if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
            // New SW installed while tab is active — notify user
            const toast = app.config.globalProperties
            if (window._aiToast) window._aiToast('新版本已就绪，刷新即可更新', 'success')
          }
        })
      })
    } catch (e) {
      // SW registration is best-effort; fail silently
    }
  }
  // Wait for the page to settle before registering
  if (document.readyState === 'complete') {
    registration()
  } else {
    window.addEventListener('load', registration)
  }
}
