# AI Provider — 项目根目录

AI API 网关/代理服务,统一管理多家 AI 供应商(OpenAI、Anthropic、商汤等)的 API Key,提供路由、熔断、Token 统计、缓存等功能。

## 启动方式

- **开发:** `python run.py` (默认 127.0.0.1:8000)
- **生产:** `start.sh` 或 `start.bat` (支持 PORT/HOST 环境变量)
- **构建 exe:** `python build_exe.py` (自动递增版本号,需先 `npm run build` 前端)

## 关键文件

| 文件 | 职责 |
|------|------|
| `run.py` | 应用入口,启动 uvicorn 服务 + 托盘图标 + 桌面 Widget |
| `main.py` | FastAPI 应用工厂,注册路由、中间件、CORS、启动/关闭事件 |
| `build_exe.py` | PyInstaller 打包脚本,自动生成版本号 |
| `conftest.py` | pytest 全局 fixture,提供测试用数据库、HTTP 客户端、测试数据 |
| `pyproject.toml` | 项目元数据与依赖声明 |
| `requirements.txt` | pip 依赖锁定 |
| `start.sh` / `start.bat` | 启动脚本,清 `__pycache__` 后启动服务 |

## 目录结构

```
api/           — FastAPI 路由层
core/          — 核心逻辑(数据库、配置、HTTP 客户端、桌面 Widget)
models/        — SQLAlchemy 数据模型
repositories/  — 数据访问层(Repository 模式)
services/      — 业务逻辑层(熔断器、负载均衡、路由等)
config/        — 配置文件
tests/         — 测试
web/           — 前端工程(Vue 3 + Vite)
docs/          — 文档
scripts/       — 工具脚本
```

## 依赖关系

- `main.py` <- `run.py` 启动
- `api/` <- `services/` + `repositories/` + `models/`
- `services/` <- `repositories/` + `models/` + `core/`
- `core/` <- `models/`(数据库)

## 常见陷阱

- 不要 kill 8000 端口上的 AIProvider.exe,否则用户服务会挂
- 启动前清 `__pycache__` (start.sh 已自动执行)
- 数据库为 SQLite,路径 `data/ai_provider.db`
- 桌面 Widget 仅 Windows 可用(依赖 pywin32)
