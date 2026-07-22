/**
 * format.js — 页面共享的格式化工具。
 * 收敛此前散落在 Accounts / ApiKeys / Logs / Mappings / LogDetailPanel
 * 各自维护的 formatTime / formatDate / formatContextLength 等重复实现。
 */

const pad = (n, l = 2) => String(n).padStart(l, '0')

/**
 * 时间戳 → 日期时间字符串。
 * @param {string} ts  形如 '2026-07-20 12:00:00[.mmm]' 的时间戳
 * @param {object} [opts]
 * @param {boolean} [opts.utc8=false]   输入按 UTC 解析、以 UTC+8 展示（日志列表用）
 * @param {boolean} [opts.seconds=false] 显示秒
 * @param {boolean} [opts.ms=false]      显示毫秒（隐含秒）
 */
export function formatTime(ts, { utc8 = false, seconds = false, ms = false } = {}) {
  if (!ts) return ''
  const parsed = new Date(utc8 ? ts.replace(' ', 'T') + 'Z' : ts.replace(' ', 'T'))
  if (isNaN(parsed.getTime())) return ts
  // utc8 模式：平移到 UTC+8 后直接读 UTC 字段，避免依赖浏览器时区
  const t = utc8 ? new Date(parsed.getTime() + 8 * 3600000) : parsed
  const get = utc8
    ? {
        y: () => t.getUTCFullYear(), mo: () => t.getUTCMonth() + 1, da: () => t.getUTCDate(),
        h: () => t.getUTCHours(), mi: () => t.getUTCMinutes(), s: () => t.getUTCSeconds(), ms: () => t.getUTCMilliseconds(),
      }
    : {
        y: () => t.getFullYear(), mo: () => t.getMonth() + 1, da: () => t.getDate(),
        h: () => t.getHours(), mi: () => t.getMinutes(), s: () => t.getSeconds(), ms: () => t.getMilliseconds(),
      }
  let out = `${get.y()}-${pad(get.mo())}-${pad(get.da())} ${pad(get.h())}:${pad(get.mi())}`
  if (seconds || ms) out += `:${pad(get.s())}`
  if (ms) out += `.${pad(get.ms(), 3)}`
  return out
}

/** 时间戳 → 仅日期（zh-CN，如 2026/07/20），无效时原样返回 */
export function formatDate(ts) {
  if (!ts) return '—'
  try {
    const d = new Date(ts)
    if (isNaN(d.getTime())) return ts
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
  } catch {
    return ts
  }
}

/** 毫秒时长 → '850ms' / '12s' / '3m 20s' / '1h 5m' */
export function formatDuration(ms) {
  if (!ms || ms <= 0) return ''
  if (ms < 1000) return `${ms}ms`
  const totalSec = Math.round(ms / 1000)
  if (totalSec < 60) return `${totalSec}s`
  const min = Math.floor(totalSec / 60)
  const sec = totalSec % 60
  if (min < 60) return sec > 0 ? `${min}m ${sec}s` : `${min}m`
  const hr = Math.floor(min / 60)
  const m = min % 60
  return m > 0 ? `${hr}h ${m}m` : `${hr}h`
}

/** 数值 → K/M 紧凑格式（token 数等） */
export function formatCompact(n) {
  if (!n) return '0'
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M'
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K'
  return String(n)
}

/** 数值 → 万/亿 中文紧凑格式（仪表盘统计） */
export function formatCn(n) {
  if (n >= 1e8) return (n / 1e8).toFixed(1) + '亿'
  if (n >= 1e4) return (n / 1e4).toFixed(1) + '万'
  return n.toLocaleString()
}

/** 上下文长度 → '128K' / '800'；空值返回 null（调用方自行兜底 '—'） */
export function formatContextLength(len) {
  if (!len) return null
  if (len >= 1000) return (len / 1000).toFixed(len % 1000 === 0 ? 0 : 1) + 'K'
  return String(len)
}

/** API Key 脱敏：保留前 10 位与后 10 位 */
export function maskKey(key) {
  if (!key || key.length < 20) return '****'
  return key.slice(0, 10) + '****' + key.slice(-10)
}

/**
 * 时间戳 → 相对时间（'刚刚' / 'n 秒前' / 'n 分钟前' / 'n 小时前'）。
 * 输入按 UTC 解析（与日志 timestamp 列一致），与浏览器时区无关。
 */
export function timeAgoUtc(ts) {
  if (!ts) return ''
  const parsed = new Date(ts.replace(' ', 'T') + 'Z')
  if (isNaN(parsed.getTime())) return ''
  const diff = Math.max(0, Date.now() - parsed.getTime())
  const sec = Math.floor(diff / 1000)
  if (sec < 60) return '刚刚'
  const min = Math.floor(sec / 60)
  if (min < 60) return `${min} 分钟前`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr} 小时前`
  return `${Math.floor(hr / 24)} 天前`
}
