# web/src — 前端源码

## 职责

前端应用源码,采用 Vue 3 Composition API 风格。

## 目录结构

```
src/
+-- api/           -- API 客户端
+-- assets/        -- 静态资源(样式)
+-- components/    -- 通用组件
|   +-- dashboard/ -- Dashboard 专用组件
|   +-- log/       -- 日志详情专用组件
+-- composables/   -- 可组合函数
+-- constants/     -- 常量定义
+-- pages/         -- 页面级组件
+-- utils/         -- 工具函数
```

## 关键约定

- 所有组件使用 <script setup> + Composition API
- 禁用选项式 API(Options API)
- 组件通过 shadcn/vue 体系构建
- 深色主题通过 Tailwind dark: 变体实现
- 路由使用 vue-router + createWebHistory

## 入口文件

- main.js — 应用入口,挂载 Vue 实例、注册路由和插件
- App.vue — 根组件,布局框架和路由出口
