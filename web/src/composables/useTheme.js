import { ref, readonly, watch, onMounted, onUnmounted } from 'vue'

// 单例状态
const currentMode = ref(localStorage.getItem('themeMode') || 'dark')
const prefersColorScheme = ref('dark')

function getSystemTheme() {
  return (
    window.matchMedia &&
    window.matchMedia('(prefers-color-scheme: light)').matches
      ? 'light'
      : 'dark'
  )
}

function applyTheme() {
  const mode = currentMode.value
  let brightness = 'dark'

  if (mode === 'light') {
    brightness = 'light'
  } else if (mode === 'system') {
    brightness = prefersColorScheme.value
  } else {
    brightness = 'dark'
  }

  document.documentElement.setAttribute('data-theme', brightness)
}

function onSystemThemeChange(e) {
  prefersColorScheme.value = e.matches ? 'light' : 'dark'
}

export function useTheme() {
  onMounted(() => {
    // 初始化系统主题检测
    prefersColorScheme.value = getSystemTheme()
    applyTheme()

    // 监听系统偏好变化
    if (window.matchMedia) {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: light)')
      mediaQuery.addEventListener('change', onSystemThemeChange)
      onUnmounted(() => mediaQuery.removeEventListener('change', onSystemThemeChange))
    }
  })

  // 当 system 模式下系统主题变化时自动同步
  watch(prefersColorScheme, () => {
    if (currentMode.value === 'system') {
      applyTheme()
    }
  })

  const setMode = (mode) => {
    currentMode.value = mode
    localStorage.setItem('themeMode', mode)
    applyTheme()
  }

  return {
    currentMode: readonly(currentMode),
    prefersColorScheme: readonly(prefersColorScheme),
    setMode,
  }
}