# ModelScope Proxy 管理后台设计

> 2026-07-16 · 设计评审

## 1. 概述

为 ModelScope Proxy 添加可视化管理后台，同时解决当前配置分散（`.env` + 代码硬编码）的问题。

### 1.1 目标

- 所有配置（账户、模型映射、系统参数）迁移到 SQLite 数据库
- 提供 Web 管理界面，支持 CRUD 操作
- 前后端分离：Python 托管静态文件 + 提供 API，前端 Vue3 编译为静态资源

### 1.2 约束

- 纯本地/内网使用，无复杂鉴权
- 前端用 npm 生态，编译为静态文件，Python 不做模板渲染
- 数据库使用 SQLite

---

## 2. 架构

```
┌─────────────────────────────────────────────────────┐
│                 用户浏览器                            │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP
┌─────────────────────▼───────────────────────────────┐
│           Python FastAPI (main.py)                   │
│  ┌─────────────┐  ┌─────────────────────────────┐   │
│  │  StaticFiles│  │  /api/admin/*  (管理 API)    │   │
│  │  (dist/*)   │  │  账户/映射/日志/统计/配置    │   │
│  └─────────────┘  └─────────────────────────────┘   │
│  /api/v1/chat/completions  (原有代理，不变)           │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│        SQLite (modelscope_proxy.db)                  │
└─────────────────────────────────────────────────────┘
```

---

## 3. 数据库设计

### 3.1 新增表

#### `accounts` — 账户配置

```sql
CREATE TABLE accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT NOT NULL UNIQUE,
    api_key TEXT NOT NULL,
    base_url TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'china',  -- china / overseas
    status TEXT NOT NULL DEFAULT 'active',  -- active / disabled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `model_mappings` — 模型别名映射

```sql
CREATE TABLE model_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_name TEXT NOT NULL,
    region TEXT NOT NULL DEFAULT 'china',  -- china / overseas
    actual_model_id TEXT NOT NULL,
    UNIQUE(alias_name, region)
);
```

#### `system_config` — 系统配置（key-value 存储）

```sql
CREATE TABLE system_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

预置 key：`log_level`, `load_balancer_strategy`, `request_timeout_ms`, `retry_count`, `auto_disable_on_quota`, `auto_reset_daily`

#### `request_logs` — 请求日志

```sql
CREATE TABLE request_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id TEXT NOT NULL UNIQUE,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    model TEXT NOT NULL,
    actual_model_id TEXT,
    account_id TEXT,
    status_code INTEGER,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    latency_ms INTEGER,
    is_stream BOOLEAN DEFAULT 0,
    error_message TEXT,
    raw_request TEXT,
    raw_response TEXT,
    INDEX(idx_logs_time) ON request_logs(timestamp),
    INDEX(idx_logs_account) ON request_logs(account_id)
);
```

### 3.2 迁移计划

- 从现有 `.env` 中的 `MODELSCOPE_ACCOUNTS_JSON` 提取数据写入 `accounts` 表
- 从 `model_mappings.json` 写入 `model_mappings` 表
- 启动时：若 `accounts` 表为空，回退读取 `.env` 并自动迁移
- `server.py` 中的硬编码账户废弃

---

## 4. 后端 API 设计

所有管理 API 前缀 `/api/admin`：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/admin/accounts` | 账户列表 |
| POST | `/api/admin/accounts` | 创建账户 |
| PUT | `/api/admin/accounts/{id}` | 更新账户 |
| DELETE | `/api/admin/accounts/{id}` | 删除账户 |
| PATCH | `/api/admin/accounts/{id}/status` | 切换状态 |
| GET | `/api/admin/mappings` | 模型映射列表 |
| PUT | `/api/admin/mappings` | 批量更新映射 |
| GET | `/api/admin/logs` | 请求日志（分页+筛选） |
| GET | `/api/admin/logs/{id}` | 日志详情 |
| GET | `/api/admin/stats` | 统计数据（热力图/趋势/模型用量） |
| GET | `/api/admin/alerts` | 告警列表 |
| GET | `/api/admin/config` | 系统配置 |
| PUT | `/api/admin/config` | 更新配置 |
| POST | `/api/admin/test` | 在线测试 |

---

## 5. 前端设计

### 5.1 技术栈

- Vue 3 + Vite
- Tailwind CSS (via @tailwindcss/vite plugin)
- shadcn/ui 通过 unplugin 集成（或直接手写，保持轻量）

### 5.2 设计风格

- **Linear Style**：深色主题 `#0e0e10`，紫色强调 `#5e6ad2`
- 内容区域全宽（无 max-width 限制），padding `p-6`
- 侧边栏宽 `w-56`，卡片 `#1a1a1e`，边框 `gray-800`

### 5.3 页面结构

| 路由 | 页面 | 核心组件 |
|---|---|---|
| `/` | 仪表盘 | 统计卡 + 账户表 + 趋势图 |
| `/accounts` | 账户管理 | 卡片列表 + 添加/编辑弹窗 |
| `/mappings` | 模型映射 | 卡片网格 + JSON 批量编辑 |
| `/logs` | 请求日志 | 多行筛选器 + 数据表格 + 详情抽屉 |
| `/stats` | 使用统计 | 热力图 + 堆叠柱状图 + 环形图 |
| `/alerts` | 告警历史 | 时间线列表 |
| `/test` | 在线测试 | 请求表单 + 响应预览 |
| `/config` | 系统配置 | 分组表单 |

### 5.4 图表

使用轻量级方案：**纯 SVG/CSS**（当前 mockup 方案），后续可升级至 `@unovis/vue` 或 `chart.js`。

---

## 6. 实施顺序

1. **数据库迁移** — 新增表 + 迁移脚本 + 从 `ConfigManager` 改为读 DB
2. **后端管理 API** — 实现 `/api/admin/*` 路由
3. **前端脚手架** — Vue3 + Vite + Tailwind 初始化
4. **前端页面开发** — 按页面列表逐个实现
5. **Python 静态托管** — FastAPI 中挂载 `StaticFiles`
6. **清理** — 废弃 `server.py`，清理硬编码配置

---

## 7. 风险与应对

| 风险 | 应对 |
|---|---|
| 数据库迁移时 `.env` 数据丢失 | 启动时自动迁移，保留 `.env` 作为回退 |
| 前端体积过大 | 使用 Vite 按需构建，不引入重型 UI 库 |
| 日志表增长快 | 定期清理 + 仅保留最近 30 天 |
