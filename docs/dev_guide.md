# 开发规范

## 数据库隔离

### 核心原则

**测试数据库与正式数据库必须完全隔离，严禁测试操作正式库。**

| 场景 | 数据库文件 | 路径 |
|---|---|---|
| 本地开发 / 自测 | `modelscope_proxy_test.db` | `./modelscope_proxy_test.db`（项目根目录） |
| 正式启动服务 | `modelscope_proxy.db` | `./modelscope_proxy.db`（项目根目录） |
| pytest 单元测试 | `tests/modelscope_proxy_test.db` | `tests/modelscope_proxy_test.db`（由 conftest 管理，每次运行后删除） |

### .env 配置规则

```bash
# 本地开发/自测时，DATABASE_URL 指向 test.db
DATABASE_URL="sqlite:///modelscope_proxy_test.db"
```

- 开发调试阶段（`python3 -m uvicorn ...`）→ `.env` 使用 `modelscope_proxy_test.db`
- 正式启动服务时 → 使用 `.env.production` 或将 `DATABASE_URL` 改为 `modelscope_proxy.db`
- **不要在同一个 .env 中切换数据库来区分测试和正式环境**——正式启动用独立的配置

### 启动方式

```bash
# 本地开发（使用 test.db）
cd /mnt/d/workspace/third
python3 -m uvicorn provider.main:app --host 0.0.0.0 --port 8000

# 正式启动（使用正式 db，通过环境变量覆盖）
DATABASE_URL="sqlite:///modelscope_proxy.db" python3 -m uvicorn provider.main:app --host 0.0.0.0 --port 8000
```

### 测试隔离规则

1. **pytest 测试**必须使用 `database` fixture（`tests/conftest.py`），该 fixture：
   - 使用独立的 `tests/modelscope_proxy_test.db`
   - 每次测试后自动删除，保证测试间无残留
2. **TestClient 集成测试**（`tests/integration/`）：
   - 必须使用独立的测试数据库，不得依赖 `.env` 指向的数据库
   - 通过 `DATABASE_URL` 环境变量在 fixture 中覆盖，而非依赖全局 `.env`
3. **手动 API 测试**（curl / Postman）：
   - 开发时使用 `modelscope_proxy_test.db`
   - 永远不要在正式库上执行测试请求

### 禁止事项

- ❌ 不要在正式库 `modelscope_proxy.db` 上运行 pytest
- ❌ 不要在 `.env` 中使用 Windows 绝对路径（如 `D:/...`），WSL 下无法访问会回退到正式库
- ❌ 不要通过删除正式库中的数据来"清理"测试污染——说明隔离失效了
- ❌ 不要共享同一份 `.env` 给测试和生产

### 数据库文件说明

| 文件 | 用途 | 是否提交 |
|---|---|---|
| `modelscope_proxy.db` | 正式运行数据 | 否（.gitignore） |
| `modelscope_proxy_test.db` | 本地开发/调试 | 否（.gitignore） |
| `tests/modelscope_proxy_test.db` | pytest 临时库 | 否（.gitignore，每次删除） |
| `modelscope_proxy.db.bak.*` | 手动备份 | 否（按需清理） |

### 迁移与初始化

- 数据库表结构变更在 `core/database.py` 的 `initialize_tables()` 中处理
- 迁移逻辑（ALTER TABLE）放在建表之后，用 `try/except OperationalError` 包裹
- 首次启动自动建表 + seed 默认配置
