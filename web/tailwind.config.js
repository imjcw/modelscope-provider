/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{vue,js,ts}',
  ],
  theme: {
    extend: {
      colors: {
        // Linear style tokens
        'ls': {
          bg: '#0e0e10',
          card: '#1a1a1e',
          elevated: '#232329',
          accent: '#5e6ad2',
          accentHover: '#6b7bf2',
          border: '#1f1f23',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'Fira Code', 'Menlo', 'monospace'],
      },
    },
  },
  plugins: [],
}
