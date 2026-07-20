# Agent 认知可观测性：Trace / Span / Event 会话模型设计

- 日期：2026-07-20
- 状态：设计定稿（本期仅领域模型设计，不实施；实施另立计划）
- 范围：trace 子域的领域模型、表结构与采集映射；可视化前端、采集埋点实现均不在本期

## 背景与目标

Agent 的故障模式与传统服务不同：没有异常堆栈、没有错误码，服务一切正常——只是推理方向偏了。传统 APM 覆盖调用链路与耗时，覆盖不到认知层：模型在哪一步、基于什么证据、做出了什么判断。典型案例：工具返回的数据只覆盖到中午 12 点，模型把上午趋势错误外推成下午的根因——错误结论人人可见，证据断裂无人能见。

目标：把一次 Agent 执行建模为 **Span + Event 树**并可持久回放，使排障者能在同一视图看到：

1. 与用户的多轮对话（每轮说了什么、答了什么）
2. 模型看到的有效上下文（窗口裁剪后的快照）
3. 每一步思维链、工具入参出参、错误现场
4. 每个 span 与 event 的起止时间、耗时、成败/超时状态
5. token 消耗分布

## 已定决策（含理由）

| 决策 | 选择 | 理由 |
|------|------|------|
| 聚合粒度 | **轮级**：Trace＝一次 `run()`/`stream()` 执行；会话大树是查询视图 | 聚合小而稳、事务边界＝请求生命周期；会话级聚合无限生长是大聚合反模式；`/agent/chat` 无会话调用同样可追踪 |
| 与 OTel 关系 | 借命名不引 SDK：`trace_id/span_id/parent_span_id/status/attributes`、`gen_ai.*` 键名对齐 OTel GenAI 语义约定 | 自建后台为主，OTel 生态红利有限；命名对齐为将来加 exporter 留门 |
| Event 语义 | **区间事件**：event 也有起止时间、耗时与成败状态；瞬时事件退化为起止相等、耗时 0 | 用户要求 event 可度量；`assistant_reply` 流式输出、`thinking` 推理阶段都有真实时长 |
| 对话记录 | 根 span 承载 `user_message` / `assistant_reply` / `context` 事件 | 回放第一视角是对话流，执行链路是下钻细节 |
| 树的领域表示 | 聚合内扁平 `list[Span]` + `parent_span_id`，`tree()` 方法按需重建嵌套 | 与行式存储一一对应、追加简单；树不变量由聚合校验 |
| 写入模式 | MVP 在 `finish()` 后整树一次落库 | 原子、简单；代价是进程崩溃丢当轮 trace，演进方向为增量 flush |

## 子域定位

新增 **trace 子域**，与 `conversation` 平级，同属「账票」限界上下文：

```
domain/trace/          聚合根 Trace、实体 Span、值对象、领域事件、仓储接口
application/trace/     （实施期）采集编排与查询用例
infrastructure/trace/  （实施期）SQLAlchemy 仓储实现
interfaces/trace/      （实施期）回放查询 API
```

与 `conversation` 子域**零直接依赖**：trace 里的 `conversation_id` 是裸 `str` 关联键（弱引用），不 import 对方值对象——遵守「跨模块只经领域事件通信」铁律。全部建模用 Pydantic v2（项目规范，禁 dataclass）；ID 生成复用 `domain/shared/id_generator.uuid7`。

## 核心模型

```
Trace（聚合根）＝ 一次 Agent 执行（一轮）
 └─ Span（内部实体，扁平列表 + parent_span_id 组树）
     └─ TraceEvent（frozen 值对象，span 内按 seq 有序追加）
```

### Trace（聚合根）

| 字段 | 类型 | 说明 |
|------|------|------|
| `trace_id` | TraceId（uuid7 hex 32） | 单调递增，列表天然时间序 |
| `conversation_id` | `str \| None` | 会话弱引用；`/agent/chat` 为 None |
| `agent_name` / `agent_version` | str | 执行主体 |
| `status` | TraceStatus | `running / ok / error / timeout / interrupted`（镜像根 span 终态） |
| `started_at` / `ended_at` | datetime | 起止时间 |
| `duration_ms` | int | 派生属性；落库冗余列 |
| `input_tokens` / `output_tokens` | int | 全轮汇总（自 model_call attributes 累加），列表页免聚合 |

### Span（内部实体，不可单独引用）

| 字段 | 类型 | 说明 |
|------|------|------|
| `span_id` | SpanId（uuid7 hex 32） | |
| `parent_span_id` | `str \| None` | None＝根；必须指向同 Trace 内已存在 span |
| `kind` | SpanKind | `turn`（根）/ `routing` / `model_call` / `tool_call` |
| `name` | str | 模型名、工具名、"turn" 等 |
| `status` | SpanStatus | `running / ok / error / timeout / interrupted` |
| `started_at` / `ended_at` | datetime | ended_at 闭合时必填 |
| `duration_ms` | int | 派生属性；落库冗余列 |
| `attributes` | dict | 开放键值；命名约定见下 |
| `events` | list[TraceEvent] | span 内有序 |

attributes 命名约定（对齐 OTel GenAI）：

- `model_call`：`gen_ai.request.model`、`gen_ai.usage.input_tokens`、`gen_ai.usage.output_tokens`
- `routing`：`routing.skill`、`routing.confidence`、`routing.fallback`、`routing.reason`
- `tool_call`：`tool.name`
- 失败摘要（任意 kind）：`error.type`、`error.message`（完整现场进 `error` 事件 payload）

### TraceEvent（frozen 值对象）

| 字段 | 类型 | 说明 |
|------|------|------|
| `seq` | int | span 内严格递增 |
| `event_type` | EventType | 见下，7 类 |
| `status` | EventStatus | `ok / error`（事件本身也可失败，如出参解析失败） |
| `started_at` / `ended_at` | datetime | 区间事件记真实起止；瞬时事件两者相等 |
| `duration_ms` | int | 派生属性；落库冗余列 |
| `payload` | str | 统一文本；JSON 由采集方序列化 |
| `truncated` | bool | 超 32KB 截断标记 |

**event_type 枚举（7 类）**：

| 类型 | 挂载 span | 区间/瞬时 | 说明 |
|------|-----------|-----------|------|
| `user_message` | turn | 瞬时 | 本轮用户输入 |
| `assistant_reply` | turn | **区间**（流式：首 token → done） | 本轮最终回复，耗时＝用户感知的输出时长 |
| `context` | turn | 瞬时 | 本轮**初始**送入模型的裁剪后上下文快照（窗口策略输出，可截断）——"模型拿到了什么证据"；ReAct 循环中间累积的输入不重复记录，可由工具事件推演 |
| `thinking` | model_call | **区间**（推理阶段） | 思维链显式捕获 |
| `tool_input` | tool_call | 瞬时 | 工具入参 |
| `tool_output` | tool_call | 瞬时 | 工具出参 |
| `error` | 任意 | 瞬时 | 异常现场（类型＋消息＋堆栈/原始响应） |

### ID 值对象

`TraceId`、`SpanId`：32 位小写 hex（`^[0-9a-f]{32}$`），`new()` 工厂内调 `uuid7().hex`——与 `ConversationId` 同构，但定义在 trace 子域内（子域自治，不跨域 import）。

## 生命周期与不变量

生命周期：`Trace.start(...)` → `begin_span()` / `record_event()` / `end_span()` → `finish()`。

1. `parent_span_id` 必须指向同一 Trace 内已存在的 Span；根 span（`parent_span_id=None`）全 trace 唯一且 kind＝`turn`
2. Span 闭合后不得再追加 Event；`error` / `timeout` / `interrupted` 均为终态
3. Event `seq` 在 span 内严格递增（append-only）；`ended_at >= started_at`（span 与 event 皆然）
4. `finish()` 时仍未闭合的 Span 被强制闭合并标 `interrupted`——异常中断现场不丢失
5. `finish()` 后 Trace 整体只读
6. `finish()` 产生领域事件 **TraceCompleted**（`trace_id`、`conversation_id`、`status`、`duration_ms`、token 合计），供未来告警/统计订阅
7. 超时语义由采集方判定：捕获 `TimeoutError` 时以 `status=timeout` 闭合对应 span

## 仓储接口（domain 定义、infrastructure 实现）

```python
class TraceRepository(Protocol):
    async def save(self, trace: Trace) -> None: ...            # append-only 整树落库
    async def get(self, trace_id: TraceId) -> Trace | None: ...
    async def list_by_conversation(self, conversation_id: str) -> list[Trace]: ...
    # trace_id 单调 → 升序即时间序，会话回放视图的数据源
```

## 表结构（PostgreSQL，3 张，append-only）

**`trace`**：`trace_id` String(32) PK、`conversation_id` String(32) NULL＋索引、`agent_name` String(128)、`agent_version` String(64)、`status` String(16)、`started_at`/`ended_at` DateTime(tz)、`duration_ms` Integer、`input_tokens`/`output_tokens` Integer、`created_at` DateTime(tz)

**`trace_span`**：`span_id` String(32) PK、`trace_id` String(32) FK＋索引、`parent_span_id` String(32) NULL、`kind` String(16)、`name` String(128)、`status` String(16)、`started_at`/`ended_at` DateTime(tz)、`duration_ms` Integer、`attributes` JSON

**`trace_event`**：`id` Integer 自增 PK（仅行存，无对外语义）、`span_id` String(32) FK＋索引、`seq` Integer、`event_type` String(16)、`status` String(8)、`started_at`/`ended_at` DateTime(tz)、`duration_ms` Integer、`payload` Text、`truncated` Boolean；UniqueConstraint(`span_id`, `seq`)

## 采集映射（论证模型充分性；实施在后续迭代）

| 现有执行环节 | 映射 |
|---|---|
| 一次 `run()`/`stream()` | 一个 Trace＋根 span（`turn`）；根 span 事件：`user_message`、`context`（窗口快照）、`assistant_reply`（流式为区间） |
| `RoutingAgentService._route()` | `routing` span；裁决结果进 attributes；识别异常 → span 内 `error` 事件（降级成功则 span 仍 `ok`——认知现场保留，链路不误报） |
| LangGraph 每次 LLM 调用 | `model_call` span；`thinking` 区间事件；`gen_ai.*` 进 attributes |
| 工具执行（tool_adapter） | `tool_call` span；`tool_input`/`tool_output` 事件；异常 → `error` 事件＋`status=error`；超时 → `status=timeout` |
| SSE token 流 | **不逐 token 记录**（体积爆炸）；`assistant_reply` 存聚合全文，区间为首 token → done |
| 会话关联 | `SendMessageUseCase` 注入 `conversation_id`；`/agent/chat` 为 NULL |

## 回放视图（5.1 案例形态）

```
会话视图（按 conversation_id 串多条 Trace，trace_id 升序＝时间序）
├─ Trace 第1轮 (turn, 4.2s, 2314 tokens, ok)
│   ├─ events: user_message("为什么昨天下午转化率跌了") / context(窗口快照) / assistant_reply(…, 流式区间)
│   ├─ routing span (0.3s)         attributes: routing.skill=data_analysis, confidence=0.91
│   ├─ model_call #1 (1.1s)        thinking("先查转化率曲线")
│   ├─ tool_call query_conversion  tool_input({date:"昨天"}) / tool_output(曲线数据)
│   ├─ model_call #2 (0.9s)        thinking("需要看支付网关指标")
│   ├─ tool_call query_timeout     tool_input(…) / tool_output(仅覆盖到12:00的数据)   ← 证据断裂点
│   └─ model_call #3 (1.2s)        thinking("有上升趋势→大概率是它导致的")            ← 推理跳跃点
└─ Trace 第2轮 …
```

## 非目标（YAGNI）与演进预留

**非目标**：可视化前端、采样率、TTL/归档、脱敏策略引擎（仅 32KB 截断＋`truncated` 标记）、OTel SDK 接入、增量 flush、逐 token 记录。

**演进预留**：attributes 命名已对齐 OTel GenAI，可加 exporter 导出标准链路；脱敏可在采集器层插策略、领域模型不动；`trace_event` 数据量大后可按 `trace` 时间分区；写入可演进为分段增量 flush（先落 running Trace，逐 span 追加）。

## 实施提示（供后续计划参考，非本期范围）

- 采集入口建议做成 `AgentService` 端口的**装饰器实现**（TracingAgentService 包裹 RoutingAgentService），对既有链路零侵入；用例层注入 `conversation_id`
- 建表沿用 `create_conversation_tables` 的 MVP 模式，正式迁移待 Alembic 接入
- 领域层测试可完全脱离 DB（聚合不变量、树重建、强制闭合语义）
