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
        // 用标准的 rgb(var(--x-rgb) / <alpha-value>) 模式，使 Tailwind 的
        // alpha 修饰符（border-ls-border/50、bg-ls-accent/10 等）对 CSS 变量颜色生效。
        //
        // 注意：不要用 color-mix() 实现——color-mix 需要 Chrome 111+ 内核，
        // 且 calc() 百分比在部分内核有解析怪癖；一旦声明被判非法丢弃，
        // 文字会回落为继承色（body 的 text-white → var(--text) 亮灰），
        // 表现为暗色主题下 dim/muted 文字全部“显示成亮色”。
        // rgb(var() / alpha) 语法 Chrome 65+ 即支持，兼容性远好于 color-mix。
        // --x-rgb 三元组在 main.css 两套主题里定义，hex 变量由三元组派生，单一数据源。
        'ls': {
          bg: 'rgb(var(--ls-bg-rgb) / <alpha-value>)',
          shell: 'rgb(var(--ls-shell-rgb) / <alpha-value>)',
          card: 'rgb(var(--ls-card-rgb) / <alpha-value>)',
          elevated: 'rgb(var(--ls-elevated-rgb) / <alpha-value>)',
          accent: 'rgb(var(--ls-accent-rgb) / <alpha-value>)',
          accentHover: 'rgb(var(--ls-accentHover-rgb) / <alpha-value>)',
          fuchsia: 'rgb(var(--ls-fuchsia-rgb) / <alpha-value>)',
          border: 'rgb(var(--ls-border-rgb) / <alpha-value>)',
          borderLight: 'rgb(var(--ls-borderLight-rgb) / <alpha-value>)',
          text: 'rgb(var(--text-rgb) / <alpha-value>)',
          dim: 'rgb(var(--text-dim-rgb) / <alpha-value>)',
          muted: 'rgb(var(--text-muted-rgb) / <alpha-value>)',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
