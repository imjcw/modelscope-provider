import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import './assets/main.css'

// ── Router ──
const routes = [
  { path: '/', name: 'dashboard', component: () => import('./pages/Dashboard.vue') },
  { path: '/accounts', name: 'accounts', component: () => import('./pages/Accounts.vue') },
  { path: '/mappings', name: 'mappings', component: () => import('./pages/Mappings.vue') },
  { path: '/logs', name: 'logs', component: () => import('./pages/Logs.vue') },
  { path: '/stats', name: 'stats', component: () => import('./pages/Stats.vue') },
  { path: '/alerts', name: 'alerts', component: () => import('./pages/Alerts.vue') },
  { path: '/test', name: 'test', component: () => import('./pages/Test.vue') },
  { path: '/config', name: 'config', component: () => import('./pages/Config.vue') },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')
