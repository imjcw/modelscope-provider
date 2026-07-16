import axios from 'axios'

// API base — works both in dev (proxy) and prod (static files served by FastAPI)
const api = axios.create({
  baseURL: '/api/admin',
  timeout: 15000,
})

// ── Accounts ──
export const getAccounts = () => api.get('/accounts')
export const createAccount = (data) => api.post('/accounts', data)
export const updateAccount = (id, data) => api.put(`/accounts/${id}`, data)
export const deleteAccount = (id) => api.delete(`/accounts/${id}`)
export const toggleAccount = (id) => api.patch(`/accounts/${id}/status`)

// ── Mappings ──
export const getMappings = () => api.get('/mappings')
export const bulkUpdateMappings = (mappings) => api.put('/mappings/bulk', { mappings })
export const deleteMapping = (alias) => api.delete(`/mappings/${alias}`)

// ── Config ──
export const getConfig = () => api.get('/config')
export const updateConfig = (config) => api.put('/config', { config })

// ── Logs ──
export const getLogs = (params) => api.get('/logs', { params })
export const getLogDetail = (id) => api.get(`/logs/${id}`)

// ── Stats ──
export const getStats = (days = 30) => api.get('/stats', { params: { days } })

// ── Alerts ──
export const getAlerts = (days = 7) => api.get('/alerts', { params: { days } })
