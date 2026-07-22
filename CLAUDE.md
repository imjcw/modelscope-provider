# CLAUDE.md

Project-specific guidance for AI assistants and contributors.

## 单元测试数据库规则（强制）

凡是涉及数据库读写单元测试，**必须**遵守以下三条，无一例外：

1. **必须使用独立的测试数据库**
   - 只能使用 `tests/conftest.py` 提供的 `database` / `db_connection` fixture，或基于 `tmp_path` 创建的临时 SQLite 文件。
   - **严禁**在测试里直接 `DatabaseManager("modelscope_proxy_test.db")` 硬编码路径，也**严禁**连接 `.env` 中 `DATABASE_URL` 指向的数据库。
   - 现有 `conftest.py` 会在导入阶段把 `DATABASE_URL` 覆盖到隔离的测试库（`tests/modelscope_proxy_test.db`），这是最后一道防线；但不要依赖它——应显式用 fixture。

2. **测试结束必须清理测试数据**
   - 优先让 fixture 自动清理（`database` fixture 会在 `yield` 后删除测试库文件）。
   - 如果测试自行建库/建表，**必须在测试结束（或 fixture teardown）里删除文件 / DROP 表**，不得把数据残留到磁盘。
   - 清理动作要放在 `yield` 之后或 `addfinalizer`，保证即使测试抛异常也会执行。

3. **禁止污染生产/共享数据**
   - 任何测试都不能以任何形式读写生产数据库。
   - 测试数据不得跨测试共享：用例之间应当相互隔离，推荐用 `tmp_path` 每个用例独立库文件；至少也要在每个用例开始前清空表。

**自检清单**（写完一个 DB 相关测试后对一遍）：
- [ ] 这个测试是通过 `database` fixture 拿到的连接吗？
- [ ] 测试结束时测试库文件/数据会被自动删除吗？
- [ ] 有没有任何硬编码路径或读取真实 `.env` 数据库的地方？

违反以上规则的测试不允许合并。
