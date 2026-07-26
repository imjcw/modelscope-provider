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
 * 点序列 → 平滑曲线路径（Catmull-Rom → 三次贝塞尔）。
 * 相比直线 polyline 观感更柔和，用于 QPS 趋势「曲线图」。
 * @param {Array<[number, number]>} pts  点数组（已按 x 升序，不含断点）
 * @returns {string} SVG path 的 d 属性
 */
export function smoothLinePath(pts) {
  if (!pts || pts.length === 0) return ''
  if (pts.length === 1) return `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`
  if (pts.length === 2) {
    return `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)} L${pts[1][0].toFixed(1)},${pts[1][1].toFixed(1)}`
  }
  const p = pts
  const n = p.length
  let d = `M${p[0][0].toFixed(1)},${p[0][1].toFixed(1)}`
  for (let i = 0; i < n - 1; i++) {
    const p0 = p[i - 1] || p[i]
    const p1 = p[i]
    const p2 = p[i + 1]
    const p3 = p[i + 2] || p2
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6
    d += ` C${cp1x.toFixed(1)},${cp1y.toFixed(1)} ${cp2x.toFixed(1)},${cp2y.toFixed(1)} ${p2[0].toFixed(1)},${p2[1].toFixed(1)}`
  }
  return d
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
