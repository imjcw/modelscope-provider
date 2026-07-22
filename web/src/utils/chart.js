/**
 * chart.js — 手写 SVG 图表的公共数学工具。
 * 项目不引入图表库（无 echarts/chart.js 依赖），Dashboard 的
 * sparkline / QPS 趋势图共用这里的点位与路径计算。
 */

/**
 * 数值序列 → SVG polyline points 字符串。
 * null/undefined 值跳过（断点不连线由调用方决定），max 兜底 1 防全零除。
 * @param {Array<number|null>} values
 * @param {number} w  视图宽度
 * @param {number} h  视图高度
 * @param {object} [opts]
 * @param {number} [opts.pad=2]  上下留白，避免折线贴边
 */
export function polylinePoints(values, w, h, { pad = 2 } = {}) {
  const pts = (values || []).filter(v => v !== null && v !== undefined)
  if (!pts.length) return ''
  const max = Math.max(...pts, 1)
  const n = values.length
  return values
    .map((v, i) => {
      if (v === null || v === undefined) return null
      const x = n > 1 ? (i / (n - 1)) * w : 0
      const y = h - pad - (v / max) * (h - pad * 2)
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .filter(Boolean)
    .join(' ')
}

/**
 * polyline points → 闭合面积路径（下边界压到 baseY）。
 * @param {string} points  polylinePoints 的输出
 * @param {number} baseY   面积底部 y
 */
export function areaPath(points, baseY) {
  if (!points) return ''
  const pts = points.split(' ').map(p => p.split(',').map(Number))
  if (!pts.length) return ''
  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x},${y}`).join(' ')
  const firstX = pts[0][0]
  const lastX = pts[pts.length - 1][0]
  return `${line} L${lastX},${baseY} L${firstX},${baseY} Z`
}

/**
 * 轴刻度取整：向上取到 1/2/5 × 10^n（如 24.8 → 30，6.2 → 10）。
 * 用于 QPS 趋势图 y 轴满量程，保证刻度是"漂亮"的数字。
 */
export function niceMax(v) {
  if (!v || v <= 0) return 1
  const exp = Math.floor(Math.log10(v))
  const base = Math.pow(10, exp)
  const frac = v / base
  const nice = frac <= 1 ? 1 : frac <= 2 ? 2 : frac <= 5 ? 5 : 10
  return nice * base
}
