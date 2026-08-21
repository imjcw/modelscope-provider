# web/public/icons — 应用图标

## 职责

存放应用图标文件,用于 PWA、桌面快捷方式、托盘图标。

## 文件说明

| 文件 | 说明 |
|------|------|
| icon-512.svg | 源文件,512x512 矢量图标 |
| icon-192.svg | 源文件,192x192 矢量图标 |
| icon-512.png | 由 SVG 生成的 512x512 PNG |
| icon-192.png | 由 SVG 生成的 192x192 PNG |

## 关键约定

- SVG 是源文件,PNG 由 SVG 通过 resvg 生成
- 修改图标时编辑 SVG,然后重新生成 PNG
- 生成 PNG: resvg -w 512 -h 512 icon-512.svg icon-512.png
