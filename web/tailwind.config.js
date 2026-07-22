/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        // Linear style tokens (CSS variable references for theme support).
        // 用 color-mix() 包装，使 Tailwind 的 alpha 修饰符
        // （border-ls-border/50、bg-ls-accent/10、hover:bg-ls-elevated/30 等）
        // 对 CSS 变量颜色生效。
        //
        // 关键：color-mix 的百分比参数必须是 <percentage>（带 % 或 0–1 的 <number>
        // 在某些引擎下被当作无效而整条声明被丢弃）。Tailwind 注入的 <alpha-value>
        // 在无修饰符时是裸 `1`、有修饰符时是 `0.5` 这类**无单位**值，Chrome 会判定
        // 为非法百分比 → 整条 color-mix 失效 → border-color 回落到 preflight 默认
        // 的 #e5e7eb（深色背景上的「白边」），bg/text 回落到黑/透明。
        // 用 calc(<alpha-value> * 100%) 强制转成合法百分比，无修饰符=100%、/50=50%。
        'ls': {
          bg: 'color-mix(in srgb, var(--ls-bg) calc(<alpha-value> * 100%), transparent)',
          shell: 'color-mix(in srgb, var(--ls-shell) calc(<alpha-value> * 100%), transparent)',
          card: 'color-mix(in srgb, var(--ls-card) calc(<alpha-value> * 100%), transparent)',
          elevated: 'color-mix(in srgb, var(--ls-elevated) calc(<alpha-value> * 100%), transparent)',
          accent: 'color-mix(in srgb, var(--ls-accent) calc(<alpha-value> * 100%), transparent)',
          accentHover: 'color-mix(in srgb, var(--ls-accentHover) calc(<alpha-value> * 100%), transparent)',
          fuchsia: 'color-mix(in srgb, var(--ls-fuchsia) calc(<alpha-value> * 100%), transparent)',
          border: 'color-mix(in srgb, var(--ls-border) calc(<alpha-value> * 100%), transparent)',
          borderLight: 'color-mix(in srgb, var(--ls-borderLight) calc(<alpha-value> * 100%), transparent)',
          text: 'color-mix(in srgb, var(--text) calc(<alpha-value> * 100%), transparent)',
          dim: 'color-mix(in srgb, var(--text-dim) calc(<alpha-value> * 100%), transparent)',
          muted: 'color-mix(in srgb, var(--text-muted) calc(<alpha-value> * 100%), transparent)',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
