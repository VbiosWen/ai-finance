# 会话唯一 ID 设计：进程内单调 UUIDv7

- 日期：2026-07-20
- 状态：设计已批准，待实施
- 范围：对话（Conversation）子域的聚合标识生成与校验

## 背景与目标

当前 `Conversation.start()`（`src/domain/conversation/aggregate.py:54`）在领域层用 `uuid4().hex` 生成会话 ID（32 位小写十六进制），以 `String(32)` 作为 `conversation` 表主键、`conversation_message` 表外键。uuid4 完全随机：ID 无法反映创建顺序，B-tree 主键插入散布全树，表持续增长后索引局部性差。

目标——会话 ID 具备**趋势递增**性质：

1. 同进程内严格递增；多实例间精确到毫秒级趋势递增。
2. ID 的字典序 = 时间序，`ORDER BY id` 即创建顺序（可作分页游标）。
3. 单字段同时充当实体唯一 ID 与数据库主键（延续现状）。
4. 外部不可枚举（保留足量安全随机位）。
5. 身份仍由聚合在领域层自生成，不依赖数据库取号。

## 非目标（YAGNI）

- 不加 `conv_` 类型前缀。
- 不引入第三方 ID 库（纯标准库实现）。
- 不迁移存量 uuid4 数据。
- 不改数据库列类型；PG 原生 `UUID` 列（16 字节）留待接入 Alembic 后评估。
- API 契约不变：对外仍是 32 字符十六进制字符串。

## 方案总览

采用 RFC 9562 UUIDv7，单调性用 Method 1（`rand_a` 12 位作毫秒内计数器）实现。改动共四处：新增领域层 ID 生成器、加固 `ConversationId` 值对象、聚合工厂改一行、接口层入参补格式校验。

### 1. ID 生成器 `src/domain/shared/id_generator.py`（新增）

纯标准库实现：`time.time_ns()` 取毫秒时间戳、`secrets`/`os.urandom` 取安全随机、`threading.Lock` 保护单调状态。零第三方依赖，符合「domain 不依赖框架」铁律；置于 `domain/shared/` 供未来 invoice、audit 等子域复用。

对外接口：`uuid7() -> uuid.UUID`。

128 位布局：

| 位段 | 宽度 | 含义 |
|------|------|------|
| unix_ts_ms | 48 | Unix 毫秒时间戳（趋势递增来源） |
| ver | 4 | 固定 `0b0111`（version 7） |
| counter | 12 | 毫秒内计数器（严格单调来源，即 RFC 的 rand_a） |
| var | 2 | 固定 `0b10`（variant） |
| rand_b | 62 | 每次生成的安全随机（不可枚举来源） |

单调性规则（持锁执行）：

- 维护全局 `(last_ms, counter)`。
- 当前毫秒 > `last_ms`：采用当前毫秒，`counter` 归零。
- 当前毫秒 ≤ `last_ms`（同毫秒并发或时钟回拨）：沿用 `last_ms`，`counter + 1`——ID 永不倒退。
- `counter` 超过 `0xFFF`（单毫秒 4096 个打满）：借下一毫秒（`last_ms + 1`），`counter` 归零。

计数器从 0 起步可预测没有关系：不可枚举性由 `rand_b` 的 62 位随机独立保证。

### 2. `ConversationId` 值对象加固 `src/domain/conversation/value_objects.py`

- `value` 字段加校验 `pattern=r"^[0-9a-f]{32}$"`，防脏数据进入领域。
- 新增类方法 `new() -> ConversationId`：内部调 `uuid7().hex`，生成职责收进值对象。
- 文档字符串「uuid4 hex」改为「uuid7 hex」。

### 3. 聚合工厂 `src/domain/conversation/aggregate.py`

`Conversation.start()` 中 `ConversationId(value=uuid4().hex)` 改为 `ConversationId.new()`；删除 `uuid4` 导入。此为聚合唯一改动。

### 4. 接口层格式校验 `src/interfaces/conversation/schemas.py`

`SendMessageBody.conversation_id` 加同样的 pattern（字段仍为 `str | None`，`None` 照旧表示新开会话，pattern 只约束传了值的情况）。效果：

- **格式非法**的入参（长度不对、非 hex、大写）由 FastAPI 在边界直接返回 **422**，不再进入用例。这是本设计唯一的 API 可见行为变化——现状是非法字符串一路进入用例、被当作未知 ID 静默新开会话，掩盖客户端 bug。
- **格式合法但不存在**的 ID 保持现有语义：`repo.get` 返回 None，用例静默新开会话。
- 领域层 `ConversationId` 的 pattern 作为第二道防线（深度防御），正常路径不会触发。

## 存储与兼容

- `uuid7().hex` 与 `uuid4().hex` 同为 32 位小写十六进制：`String(32)` 主键、外键、`(conversation_id, seq)` 唯一索引全部不动，**零迁移**。
- 十六进制定长编码保序：hex 字符串字典序 = 128 位数值序 = 时间序。
- 存量 uuid4 数据同为 32 位小写 hex，通过新校验，仓储重建聚合（`repository.py` 的 `_to_conversation`）不受影响；新旧 ID 共存无冲突。「按 ID 排序 = 按时间排序」仅对切换后的新数据成立，存量排序仍以 `created_at` 为准。

## 测试计划

新增 `tests/test_id_generator.py`：

- 连续生成 N 个，数值与 hex 字典序均严格递增。
- version 位 = 7、variant 位 = `0b10`。
- `.hex` 为 32 位小写十六进制。
- 多线程并发生成无重复、各线程内递增。
- 计数器打满借毫秒路径（可用小步循环压出同毫秒场景验证不重复不倒退）。

改造 `tests/test_conversation_value_objects.py`：

- `ConversationId.new()` 产出合法格式且两次生成递增。
- 合法 32 位 hex 通过；非法值（`"abc"`、大写、31/33 位）抛 `ValidationError`。
- 现有 `ConversationId(value="abc")` 断言相应删除。

夹具修正（手造 ID 改为合法 32 位 hex）：

- `tests/test_conversation_aggregate.py:73` — `ConversationId(value="c1")`。
- `tests/test_conversation_repository.py:82` — `ConversationId(value="不存在")`（改为合法但库中不存在的 hex）。
- 领域事件与 DTO（`ConversationStarted(conversation_id="c1")`、`ChatResult(conversation_id="conv-1")` 等）字段是普通 `str`，不受影响，不改。
- 路由测试若有以非法格式 `conversation_id` 请求体走 422 之外路径的用例，一并对齐（实施时排查）。

验收标准：全部既有测试 + 新增测试通过（`uv run python -m unittest discover -s tests`）。

## 影响面清单

| 文件 | 改动 |
|------|------|
| `src/domain/shared/id_generator.py` | 新增：单调 uuid7 生成器 |
| `src/domain/conversation/value_objects.py` | `ConversationId` 加 pattern 校验 + `new()` 工厂 |
| `src/domain/conversation/aggregate.py` | `start()` 改用 `ConversationId.new()`，删 `uuid4` 导入 |
| `src/interfaces/conversation/schemas.py` | `SendMessageBody.conversation_id` 加 pattern |
| `tests/test_id_generator.py` | 新增 |
| `tests/test_conversation_value_objects.py` | 改造 ID 校验断言 |
| `tests/test_conversation_aggregate.py`、`tests/test_conversation_repository.py` | 夹具 ID 修正 |
