# web — 前端工程(Vue 3 + Vite)

## 职责

提供管理后台 Web UI 和 PWA 支持。

## 技术栈

- Vue 3 (Composition API + <script setup>)
- Vite 构建工具
- Tailwind CSS 样式
- shadcn/vue 组件体系
- Chart.js 图表

## 文件说明

| 文件/目录 | 职责 |
|-----------|------|
| src/ | 前端源码 |
| public/ | 静态资源(图标、manifest.json、Service Worker) |
| index.html | 入口 HTML |
| vite.config.js | Vite 构建配置 |
| tailwind.config.js | Tailwind 主题配置 |
| postcss.config.js | PostCSS 配置 |
| favicon.ico | 网站 favicon |
| sw.js | Service Worker(PWA 离线支持) |

## 关键约定

- 使用 shadcn/vue 组件体系,禁用 Tailwind 内联 CSS 以外的样式方案
- 组件命名: PascalCase
- 页面路由: /(Dashboard)、/accounts、/logs、/config 等
- 后端 API 路径: /api/admin/*

## 构建

```bash
cd web && npm run build
```
