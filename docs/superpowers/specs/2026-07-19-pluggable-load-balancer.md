# 可插拨负载均衡策略设计

**日期**: 2026-07-19
**状态**: 草稿
**分支**: batch-task-5-8

## 1. 背景与目标

### 现状

`services/load_balancer.py` 中的 `LoadBalancer.select_account()` 内部硬编码了 round-robin 选择逻辑。`core/database.py` 的 `system_config` 表已预留配置项 `load_balancer_strategy`（可选值描述 `round_robin/least_conn/random`），但从未被任何代码读取——是一段死配置。此外，`api/routes.py:get_services()` 在每次请求都重新构造 `LoadBalancer`，导致任何有状态策略（如 round-robin 的 `current_index`）无法跨请求保持。

### 目标

- 把选择逻辑抽为**策略模式**，支持四种可插拨策略：`round_robin`、`random`、`least_conn`、`failover`
- 通过 `system_config.load_balancer_strategy` 配置切换策略
- 修复"每请求重建 LoadBalancer 导致状态丢失"的问题，让策略实例跨请求保持状态
- `least_conn` 策略支持通过 `@contextmanager` 跟踪请求生命周期，统计每个账户的活跃连接数
- **不改变** `LoadBalancer` 公开接口（`__init__` 签名、`select_account(model_name)`），保证现有调用方（`admin_service.py`、所有测试）零破坏
- **不引入**请求级重试（retry 是调用方职责，proxy 只负责按策略选一个账户打出去）

### 非目标

- 不加新的前端 UI（策略通过现有系统配置 / DB 直接写入）
- 不做滑动窗口健康判断（本期复用 `unavailable_models`，未来可迭代）
- 不修改 `openai_proxy.py`（非生产路径）
- 不做请求级超时 / 重试逻辑

## 2. 架构设计

### 2.1 总体分层

```
┌─────────────────────────────────────────────────────┐
│  api/routes.py : chat_completions()                 │
│    load_balancer.select_account(model_name)         │
│    with load_balancer.request_context(account):     │
│        ... forward / parse / return ...             │
└───────────────┬─────────────────────────────────────┘
                │ 公开接口（不变）
                ▼
┌─────────────────────────────────────────────────────┐
│  LoadBalancer (facade)                              │
│    ① supplier_model_filter                          │
│    ② health_filter (unavailable_models)             │
│    ③ strategy.select(available_candidates)          │
│    + request_context(account) → strategy 的 ctx     │
└───────────────┬─────────────────────────────────────┘
                │ 委托选择
                ▼
┌─────────────────────────────────────────────────────┐
│  SelectionStrategy (ABC)                            │
│    select(candidates) -> account                    │
│    request_context(account_id) -> ContextManager    │
│                                                     │
│  RoundRobinStrategy   有状态 _index                 │
│  RandomStrategy       无状态                        │
│  LeastConnStrategy    有状态 _active: Counter       │
│  FailoverStrategy     无状态                        │
└─────────────────────────────────────────────────────┘
```

### 2.2 关键决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 策略接口粒度 | `select(candidates)` 只做最终选择 | supplier filter + health filter 集中维护，策略不重复 |
| 策略状态生命周期 | 长期单例（存 `app.state.services`） | round-robin 需跨请求保持 index；least_conn 需保持连接计数 |
| 账户列表生命周期 | 每请求刷新（从 DB 读） | 保持现有行为（新加账户立即生效） |
| 健康判断 | 复用 `unavailable_models` | "先简单后迭代" |
| 请求生命周期跟踪 | `@contextmanager` on 策略 | 仅 LeastConn 覆写；其他策略用 `nullcontext()` 无操作 |
| 默认策略 | `round_robin` | 兼容现有行为 |
| 非法配置值 | 回退 `round_robin` | 防御性，不报错 |

## 3. 组件详设

### 3.1 `services/selection_strategies.py`（新建）

```python
class SelectionStrategy(ABC):
    @abstractmethod
    def select(self, candidates: List[ModelScopeAccount]) -> ModelScopeAccount:
        """从过滤后的候选列表中选一个账户。"""
        ...

    @contextmanager
    def request_context(self, account_id: str):
        """请求生命周期跟踪。默认无操作，least_conn 覆写。"""
        yield
```

**`RoundRobinStrategy`**
- 状态：`_index: int = 0`
- `select`: `candidates[_index % len(candidates)]`，然后 `_index += 1`
- `request_context`: 继承默认（`yield` 无操作）

**`RandomStrategy`**
- 无状态
- `select`: `random.choice(candidates)`

**`LeastConnStrategy`**
- 状态：`_active: Counter[str]`（用 `collections.Counter`）
- `select`: `min(candidates, key=lambda a: _active[a.account_id])`
- `request_context(account_id)`:
  ```python
  self._active[account_id] += 1
  try:
      yield
  finally:
      self._active[account_id] -= 1  # 保证异常时也递减
  ```

**`FailoverStrategy`**
- 无状态
- `select`: `return candidates[0]`
- 语义：账户列表按 ID 排序（DB `ORDER BY id`），health filter 已移除不健康账户，所以 `candidates[0]` 始终是"当前健康主节点"；主节点被摘除后，下一个自然成为主节点，调用方视角即"主挂了自动转备"

**`StrategyFactory`**
```python
class StrategyFactory:
    _registry: Dict[str, Type[SelectionStrategy]] = {
        "round_robin": RoundRobinStrategy,
        "random": RandomStrategy,
        "least_conn": LeastConnStrategy,
        "failover": FailoverStrategy,
    }

    @classmethod
    def create(cls, name: str) -> SelectionStrategy:
        if not isinstance(name, str):
            return RoundRobinStrategy()
        strategy_cls = cls._registry.get(name.strip().lower(), RoundRobinStrategy)
        return strategy_cls()
```

### 3.2 `services/load_balancer.py`（重构）

**公开接口不变**：
```python
class LoadBalancer:
    def __init__(
        self,
        accounts: List[ModelScopeAccount],
        supplier_model_repo=None,
        strategy: SelectionStrategy = None,
    ):
        self.accounts = accounts
        self.supplier_model_repo = supplier_model_repo
        self.strategy = strategy or RoundRobinStrategy()

    def select_account(self, model_name: str = None) -> ModelScopeAccount:
        ...

    @contextmanager
    def request_context(self, account):
        with self.strategy.request_context(account.account_id):
            yield
```

`select_account` 内部逻辑：

1. 空列表 → `ValueError("No accounts available for load balancing")`
2. supplier model filter（现有逻辑不变）
3. health filter（现有逻辑不变）：`[acc for acc in candidates if acc.unavailable_models is None or model_name not in acc.unavailable_models]`
4. 全被过滤 → `ValueError("All accounts are unavailable for model ...")`
5. **原来硬编码的 `available_accounts[self.current_index % len(...)]` 替换为** `self.strategy.select(available)`

迁移：`current_index` 字段删除，状态移入 `RoundRobinStrategy._index`。

### 3.3 `core/service_init.py`（改动）

在 `initialize_all()` 中创建策略单例并存入 services：

```python
from services.selection_strategies import StrategyFactory
from repositories.config_repository import ConfigRepository

config_repo = ConfigRepository(database)
strategy_name = config_repo.get("load_balancer_strategy") or "round_robin"
strategy = StrategyFactory.create(strategy_name)

services["strategy"] = strategy
services["load_balancer"] = LoadBalancer(
    accounts, supplier_model_repo=supplier_model_repo, strategy=strategy
)
```

注：`ConfigRepository` 已在文件顶部导入但未使用，现启用。

### 3.4 `api/routes.py`（改动）

**`get_services()`（line 150）**：从复用 `app.state.services["strategy"]` 替换新建 LoadBalancer：

```python
strategy = services.get("strategy") or RoundRobinStrategy()
load_balancer = LoadBalancer(
    accounts, supplier_model_repo=supplier_model_repo, strategy=strategy
)
```

**`chat_completions()`（line 344 后）**：用 `with` 包裹请求生命周期。非流式与流式需要**不同的包裹方式**：

**非流式**（简单 `with`，覆盖整个 await）：

```python
selected_account = load_balancer.select_account(request.model)
with load_balancer.request_context(selected_account):
    actual_model_id = await alias_resolver.resolve_alias(selected_account, request.model)
    response = await http_client.request(selected_account, "POST", url, json=request_body)
    # ... parse / convert / return 全部在 with 内
```

`request_context` 计数器覆盖整次上游 HTTP 请求（连接建立 → 响应完整到达 → 解析）——这就是"连接"语义。

**流式**（需要 async generator wrapper，因为 `stream_response_with_logging` 是 async generator，`StreamingResponse` 要等客户端消费时才迭代）。错误的做法：

```python
# ❌ with 在 generator 创建后立刻退出，不会覆盖流式传输过程
with load_balancer.request_context(selected_account):
    return StreamingResponse(stream_response_with_logging(...), ...)  # 计数器已被递减
```

正确的做法：新增一个 async generator wrapper 把 `with` 包在迭代之内（`api/routes.py` 内）：

```python
async def _stream_with_context(load_balancer, account, inner_gen):
    """用 request_context 包裹流式迭代，保证计数器覆盖客户端消费全流的过程。"""
    with load_balancer.request_context(account):
        async for chunk in inner_gen:
            yield chunk
```

然后在 `chat_completions()` 的 streaming 分支：

```python
selected_account = load_balancer.select_account(request.model)
actual_model_id = await alias_resolver.resolve_alias(selected_account, request.model)
return StreamingResponse(
    _stream_with_context(
        load_balancer,
        selected_account,
        stream_response_with_logging(
            selected_account, http_client, request.model, request_body,
            actual_model_id, admin_service, quota_updater=quota_updater,
            client_key_name=client_key_name,
        ),
    ),
    media_type="text/event-stream",
)
```

这样 `least_conn` 的计数器准确反映"该账户上有多少客户端正在消费流"。

### 3.5 `core/database.py`（改动）

更新种子配置描述，加入 `failover`：

```python
("load_balancer_strategy", "round_robin", "负载均衡策略: round_robin/random/least_conn/failover"),
```

## 4. 数据流

### 4.1 请求路径（含新策略）

```
Client → POST /v1/chat/completions
  │
  ├─ get_services()
  │    ├─ DB 读取账户列表 → accounts
  │    ├─ 复用 app.state.services["strategy"]
  │    └─ LoadBalancer(accounts, supplier_repo, strategy)  ← 新 balancer，老 strategy
  │
  ├─ load_balancer.select_account(model)
  │    ├─ supplier_model_filter
  │    ├─ health_filter (unavailable_models)
  │    └─ strategy.select(candidates)  ← 策略决定最终账户
  │
  ├─ with load_balancer.request_context(selected_account):  ← least_conn 开始计数
  │    ├─ resolve_alias
  │    ├─ http_client.request → ModelScope
  │    ├─ parse response
  │    └─ return to client
  └─ with 退出  ← least_conn 结束计数
```

### 4.2 启动时策略创建

```
ServiceInitializer.initialize_all()
  ├─ database.seed_default_config()  ← 写入 load_balancer_strategy = "round_robin"
  ├─ ConfigRepository.get("load_balancer_strategy")  ← 读取
  ├─ StrategyFactory.create(name)  ← 实例化
  └─ services["strategy"] = strategy  ← 存为长期单例
```

## 5. 错误处理

| 错误场景 | 处理方式 |
|----------|----------|
| `load_balancer_strategy` 配置缺失 | 默认 `"round_robin"` |
| `load_balancer_strategy` 值为非法字符串 | `StrategyFactory` 回退 `RoundRobinStrategy` |
| 策略实例化抛异常 | 不应发生（工厂内不含 I/O）；若发生，让异常上浮让管理员看到 |
| 策略 `select()` 时 candidates 为空 | `LoadBalancer` 在调用 `strategy.select()` 前已 `raise ValueError`，策略永远收到非空列表 |
| `least_conn` 的 `request_context` 内请求抛异常 | `finally` 块保证 `_active` 递减，不会泄漏计数 |

## 6. 影响分析

### 6.1 接口兼容性

| 调用方 | 是否破坏 | 说明 |
|--------|----------|------|
| `admin_service.py:185` `LoadBalancer(accounts_for_alias)` | ❌ 不破坏 | 未传 strategy → 默认 `RoundRobinStrategy()`，行为同旧 |
| `api/routes.py:150` `LoadBalancer(accounts, supplier_model_repo=...)` | ❌ 不破坏 | 接口签名兼容，新增 strategy 参数可选 |
| `tests/services/test_load_balancer.py` | ❌ 不破坏 | `LoadBalancer(accounts)` / `select_account()` 不变 |
| `tests/services/test_load_balancer_model_filter.py` | ❌ 不破坏 | 同上 |
| `tests/integration/test_full_flow.py` | ❌ 不破坏 | 同上 |

### 6.2 行为变化

| 策略 | 旧行为 | 新行为 |
|------|--------|--------|
| round_robin | 每请求 index 重置 → 永远选第一个可用 | 真正跨请求轮转 |
| random | 不存在 | 新增 |
| least_conn | 不存在 | 新增，按活跃连接数分配 |
| failover | 不存在 | 新增，主备模式 |

### 6.3 `_active` 内存说明

`LeastConnStrategy._active` 是 `Counter[str]`，键为 `account_id`。账户被从 DB 删除后，其 ID 仍留在 Counter 中（值为 0）。影响极小（每个残留 ID 约 72 字节）。**不在本期做清理**；如需清理可在后续迭代加入定期 sweep 或懒清理。

## 7. 测试计划

### 7.1 新增测试（`tests/services/test_selection_strategies.py`）

- `RoundRobinStrategy`：3 个账户，连续 6 次 `select`，验证分布为 A,B,C,A,B,C
- `RandomStrategy`：验证每次调用返回有效账户，多次调用覆盖所有账户
- `LeastConnStrategy`：验证 `select` 选最少连接账户；`request_context` 进出时计数正确；异常时也递减
- `FailoverStrategy`：验证永远选 `candidates[0]`；摘除第一个后自动选第二个
- `StrategyFactory`：合法名 / 非法名 / `None` / 非字符串 / 大小写混合

### 7.2 修改现有测试

- `tests/services/test_load_balancer.py`：无需修改（测试通过 `LoadBalancer(accounts)` 构造，走默认策略）

### 7.3 回归

`pytest tests/` 全部通过。

## 8. 文件改动清单

| 文件 | 动作 | 说明 |
|------|------|------|
| `services/selection_strategies.py` | 新增 | 策略接口 + 4 策略 + 工厂 |
| `services/load_balancer.py` | 重构 | facade 化，委托策略 |
| `core/service_init.py` | 改动 | 创建策略单例，写入 services["strategy"] |
| `api/routes.py` | 改动 | 复用策略；chat_completions 加 `with request_context` |
| `core/database.py` | 改动 | 种子配置描述加 `failover` |
| `tests/services/test_selection_strategies.py` | 新增 | 策略单测 |

## 9. 风险与回滚

| 风险 | 缓解 |
|------|------|
| 策略实例跨请求共享状态在多 worker 部署下不协调 | 当前部署为单进程 + async，非多 worker；若后续改多 worker，策略是每个 worker 独立实例，不影响正确性 |
| least_conn 计数因异常未递减 | `try/finally` 保证递减 |
| least_conn `_active` 只增不减（账户 ID 残留） | `Counter` 不自动清理；账户被删除后其 ID 仍占少量内存，可忽略；若需清理可加定期 sweep（不在本期） |
| 回滚 | 删除 `services/selection_strategies.py`，恢复 `load_balancer.py` 旧版，`routes.py`/`service_init.py/database.py` 改动是可逆的单行修改 |

## 10. 后续迭代（不在本期）

- 滑动窗口健康判断：替换 `unavailable_models` 为近 N 次请求的成功率/RT 统计
- 前端 UI 暴露策略切换入口
- 策略权重（weighted round_robin / weighted least_conn）
- 请求级重试（独立能力，调用方也可做）
