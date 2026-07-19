/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        // Linear style tokens (now CSS variable references for theme support)
        'ls': {
          bg: 'var(--ls-bg)',
          card: 'var(--ls-card)',
          elevated: 'var(--ls-elevated)',
          accent: 'var(--ls-accent)',
          accentHover: 'var(--ls-accentHover)',
          border: 'var(--ls-border)',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
