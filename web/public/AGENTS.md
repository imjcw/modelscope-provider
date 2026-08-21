# web/public — 前端静态资源

## 职责

存放前端静态资源,包括应用图标、PWA 配置、Service Worker。

## 文件说明

| 文件 | 职责 |
|------|------|
| manifest.json | PWA Manifest,定义图标、名称、主题色 |
| sw.js | Service Worker,使用 network-first 策略 |
| icons/ | 应用图标(SVG 源文件 + PNG 生成文件) |

## 关键约定

- Service Worker 使用 network-first 策略,避免缓存过期导致 Failed to fetch
- 图标源文件为 SVG,PNG 由 SVG 生成,不直接编辑 PNG
- manifest.json 中引用 /web/icons/ 路径
