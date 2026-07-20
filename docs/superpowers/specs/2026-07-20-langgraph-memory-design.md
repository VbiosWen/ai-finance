# LangGraph 记忆接管:checkpointer 多轮记忆与会话模型纯存储化设计

- 日期:2026-07-20
- 状态:已与用户逐节评审通过,待实施
- 关联:反转 [2026-07-19 对话子域设计](2026-07-19-conversation-aggregate-design.md) 的决策 D3;不影响 [2026-07-20 Trace 可观测性设计](2026-07-20-trace-observability-model-design.md)(conversation_id 弱引用不变)

## 1. 背景与目标

7-19 设计的 D3 决策把对话历史真相源放进 `Conversation` 聚合,LangGraph 被刻意降级为无状态执行器(`enable_memory=False`),每轮由 `ContextWindowPolicy` 裁窗、把纯文本历史整窗回放给 Agent。运行下来暴露三个问题:

1. **记忆降真**:每轮只回放 user/assistant 纯文本,ReAct 的工具调用与结果消息在轮间丢失,Agent 无法参考上一轮"查过什么、查到什么";
2. **自研负担**:窗口维护、历史回放是自己造的记忆机制,而 LangGraph checkpointer 是框架原生能力;
3. **上下文工程无处安放**:想做"每轮对话/工具调用的压缩"这类逐轮上下文规划,现有链路没有干净的扩展点。

目标:**记忆归 LangGraph,事实归领域**——

- 多轮工作记忆由 LangGraph checkpointer(PostgreSQL 持久化)按 `thread_id = conversation_id` 维护,全量图状态跨轮保真;
- `Conversation` 聚合退化为**纯存储**:append-only 审计留痕、ACTIVE/CLOSED 状态机、领域事件出口,不再喂 LLM;
- 意图路由移入图内,并提供**中间件插槽**作为逐轮上下文工程(压缩/规划)的稳定扩展点。

## 2. 关键决策(已与用户确认)

| # | 决策 | 结论 | 理由 |
|---|---|---|---|
| N1 | 记忆存储 | **AsyncPostgresSaver**(`langgraph-checkpoint-postgres`) | 项目已有 PostgreSQL;重启不丢、跨进程;MemorySaver 重启失忆,回灌方案记忆降真且多一套逻辑 |
| N2 | 架构形态 | **单一 `create_agent` 图 + 中间件管道** | 技能差异目前仅在 system_prompt(`tools=[]`),动态 prompt 完全覆盖;middleware 是 langchain 1.x 一等扩展机制,内置 Summarization/ContextEditing 两个压缩件直接可用;单 checkpoint 命名空间状态最简。备选"父图+每技能子图"在技能异构前是纯复杂度(YAGNI),将来单个技能长成异构图时再拆子图演进 |
| N3 | 路由位置 | **图内**,`RoutingMiddleware` 承载 | 路由天然读到 checkpointer 回放的(压缩后)完整历史,"继续""那第二个呢"等短指代路得准;domain `RoutingPolicy` 原样复用 |
| N4 | 上下文工程扩展点 | **`AgentMiddleware` 接口 + 装配插槽 `context_middleware`** | 用户要"逐条规划对话、每轮/工具调用压缩";`before_agent`(轮级)/`before_model`(逐次调用)/`wrap_tool_call`(工具出参)三钩子全覆盖,压缩结果持久回写 checkpoint |
| N5 | `/agent/chat` 行为 | **变为纯无状态**,不再透传客户端 thread_id 进图 | Agent 带上 checkpointer 后,透传任意 thread_id 等于允许绕过会话端点续聊/撞入他人会话记忆;多轮一律走 `/conversations/messages` |
| N6 | 一致性模型 | checkpoint 与审计表**两次独立提交**,失败返 500 + 日志,接受短暂漂移 | 同库不同表但 LangGraph 自管连接,无跨表事务可用;MVP 与现状"save 失败则事件不发"同级,演进方向 outbox/对账 |

### 与 7-19 设计的决策差异(记录在案)

D3"领域拥有历史、LangGraph 无状态"被本设计反转。7-19 用 D3 换来的「审计/事件干净」不受损——审计与事件仍由 `Conversation` 聚合提供;被放弃的是「领域是喂 LLM 的唯一真相源」,换来记忆保真与框架原生上下文工程能力。自此系统存在**两份对话数据**:checkpoint(工作记忆,含工具消息与摘要)与 conversation 表(业务事实),以后者为审计口径。

## 3. 范围

**In scope**

- `infrastructure/ai/middleware/`:`RoutingMiddleware` 自研;压缩中间件装配;
- `build_conversation_agent()` 单图装配工厂,替代 `skill_agent_builder`;
- `AsyncPostgresSaver` 接入(依赖、连接、启动建表、生命周期);
- `SendMessageUseCase` 简化(只喂最新一条)、仓储 `get_head()`;
- `/agent/chat[/stream]` 无状态化;SSE `routing` 首帧改从图事件流映射;
- 退役:`RoutingAgentService`、`AgentRegistry`、`ContextWindowPolicy`、每技能一图装配;
- `LangChainAgentService` 从 `interfaces/ai` 归位 `infrastructure/ai`(修 7-19 设计 §12 遗留债,本次动装配顺手完成)。

**Out of scope(后续独立 spec)**

- 具体压缩策略的自研实现(本设计只交付插槽与契约);
- 工具接入后的按技能工具子集动态绑定(`wrap_model_call` 已预留);
- `/conversations/messages` 的流式版本;
- checkpoint 的 TTL/归档/对账、outbox;
- 跨会话长期记忆(LangGraph Store / langmem)。

## 4. 架构总览

```
POST /conversations/messages
   │
   ▼
SendMessageUseCase                       ← 只喂最新一条
   │  convo = repo.get_head(cid) / Conversation.start()   ← 领域把门(存在性+ACTIVE)
   │  convo.post_user_message(content)
   │  agent.run(AgentRequest([最新消息], thread_id=convo.id))
   │            │
   │            ▼  单一 create_agent 图(checkpointer=AsyncPostgresSaver)
   │      ┌─ 回放 checkpoint(全史:工具消息、摘要、路由通道)
   │      ├─ RoutingMiddleware.abefore_agent  → 意图识别 + RoutingPolicy 裁决 → 写 state
   │      ├─ context_middleware 插槽(Summarization / ContextEditing / 自研)
   │      ├─ ReAct 循环(awrap_model_call 按裁决动态渲染技能 prompt)
   │      └─ checkpoint 落 Postgres
   │  convo.record_assistant_message(reply)
   │  repo.save() + publisher.publish()
   ▼
ChatResult
```

### 组件去留

| 组件 | 层 | 去向 |
|---|---|---|
| `RoutingAgentService` | application | 退役——编排移入 `RoutingMiddleware` |
| `AgentRegistry` | application | 退役——技能目录由 middleware 持有(同源 Nacos 配置) |
| `skill_agent_builder`(每技能一图) | infrastructure | 改写为 `build_conversation_agent()` |
| `ContextWindowPolicy` | domain | 退役——职责移交压缩中间件 |
| `RoutingPolicy` / `AgentPromptConfig` | domain | 原样保留,被 middleware 调用 |
| `LlmIntentRecognizer` / `IntentRecognizer` 端口 | infra / application | 原样保留 |
| `Conversation` 聚合、仓储、领域事件 | domain / infra | 保留,职责收窄为纯存储+事件 |
| `LangChainAgentService` | interfaces/ai → **infrastructure/ai** | 保留并归位;仍是"喂 messages→回 reply"适配器 |
| `SendMessageUseCase` | application | 简化;`thread_id` 恢复"驱动记忆"语义 |

**DDD 合规**:middleware 是 LangChain 框架类型,全部住 `infrastructure/ai/middleware/`;向内调用 domain(`RoutingPolicy`、`AgentPromptConfig`)与 application 端口(`IntentRecognizer`),依赖方向不破;domain 除删除 `ContextWindowPolicy` 外零改动。

## 5. 图状态与中间件契约

### 5.1 状态(随 checkpoint 持久化)

```python
class RoutingState(AgentState):          # RoutingMiddleware.state_schema
    routed_skill: str | None = None      # 本轮裁决技能
    routing_confidence: float = 0.0
    routing_fallback: bool = False
```

`messages` 通道由 LangGraph 维护:用户/助手消息、工具调用与结果消息、压缩摘要。路由决策通道随 checkpoint 留痕,天然可回放。

### 5.2 RoutingMiddleware(自研)

构造注入:`IntentRecognizer` 实现、`RoutingPolicy`、`AgentIdentity`、`list[SkillConfig]`。

- `abefore_agent`(每轮一次):取 `state["messages"]` 尾部 8 条(装配参数可调,意图识别不需要全史)→ `recognizer.recognize(messages, catalog)` → `policy.decide(cls, available)` → 决策写 state。识别异常 → 兜底 `general`,对话不中断(沿用现有降级语义)。
- `awrap_model_call`(每次模型调用):按 `state["routed_skill"]` 用 `AgentPromptConfig(identity, [skill]).render()` 替换 system_prompt;未来在此处换技能工具子集。

### 5.3 上下文工程扩展点(压缩/规划)

```python
def build_conversation_agent(
    *, llm, identity, skills, recognizer, policy,
    checkpointer,
    context_middleware: Sequence[AgentMiddleware] = (),   # ← 插槽
): ...
# 中间件链固定顺位:[RoutingMiddleware, *context_middleware],路由永远最先
```

- **开箱即用**:`SummarizationMiddleware(model=llm, trigger=token 阈值, keep=最近 N)`——超阈值把旧轮替换为摘要,持久回写 checkpoint,压缩一次终身受益;`ContextEditingMiddleware(edits=[ClearToolUsesEdit(...)])`——清理旧工具结果(接入工具后启用)。
- **自研策略** = 实现 `AgentMiddleware` 子类,三个钩子覆盖逐轮上下文工程:
  - `abefore_agent`:轮级规划,每轮进场先整理记忆;
  - `abefore_model`:逐次模型调用前重写 messages(返回 `RemoveMessage` + 摘要消息即持久生效);
  - `awrap_tool_call`:工具出参当场压缩。
- 压缩参数(阈值/保留条数)挂 Nacos `llm-config` 新增 `summarization` 节(摘要与对话共用同一 LLM,配置同源),watcher 热更新。

## 6. 用例与一致性

### 6.1 SendMessageUseCase(简化后)

```python
async def execute(self, cmd: SendMessageCommand) -> ChatResult:
    convo = None
    if cmd.conversation_id:
        convo = await self._repo.get_head(ConversationId(value=cmd.conversation_id))
    if convo is None:
        convo = Conversation.start(cmd.agent_id)

    convo.post_user_message(cmd.content)                  # 领域把门:CLOSED 抛异常
    response = await self._agent.run(AgentRequest(
        messages=[{"role": "user", "content": cmd.content}],   # 只喂最新一条
        thread_id=convo.id.value,                              # 驱动 checkpointer 记忆
    ))
    convo.record_assistant_message(response.reply)

    await self._repo.save(convo)
    for ev in convo.pull_events():
        await self._publisher.publish(ev)
    return ChatResult(conversation_id=convo.id.value, reply=response.reply)
```

仓储新增 `get_head(cid)`:只加载对话头(id/agent/status/时间戳),不载消息——聚合不变量本就不依赖历史(7-19 设计 §5.3),追加照常。原 `get(window=N)` 保留给审计/查询读路径。

### 6.2 一致性模型

- **工作记忆真相源** = checkpoint;**业务事实源** = conversation 表。同库不同表,两次独立提交,无跨表事务。
- 失败窗口:图执行成功、审计落库失败 → 请求 500,记忆已前进、审计缺当轮;用户重发会在记忆里多一条重复 user 消息。MVP 接受并记 error 日志,演进方向 outbox/对账。
- `CLOSED` 校验发生在进图之前:关闭的会话记忆侧自然冻结,不变量仍由领域把门。

## 7. 接口层行为

| 端点 | 变化 |
|---|---|
| `POST /conversations/messages` | 入参出参不变;记忆保真度提升(工具中间消息跨轮保留)、长对话自动压缩 |
| `POST /agent/chat[/stream]` | ⚠️ **breaking**:不再把客户端 `thread_id` 透传进图 config,纯无状态单发;`thread_id` 字段保留仅作日志关联;多轮请走 `/conversations/messages` |
| SSE `routing` 首帧 | 帧格式不变、前端无感;来源改为图事件流:`_map_event` 侦听 `RoutingMiddleware.abefore_agent` 节点的 `on_chain_end`(output 含 `routed_skill`)映射为 routing 帧;若实施期事件名不可稳定辨识,回退为 middleware 内用 LangGraph custom stream writer 显式发射 |

## 8. 基础设施与装配

- 依赖:`uv add langgraph-checkpoint-postgres`(自带 psycopg3;与 SQLAlchemy asyncpg 引擎互不干扰,各管各的连接)。
- `bootstrap/container.py`:Nacos `postgres` 配置同源取 DSN → `AsyncPostgresSaver`(独立 psycopg 连接池)→ 启动 `checkpointer.setup()` 建表(沿用 `create_conversation_tables` 的 MVP 建表模式,正式迁移待 Alembic)→ 注入 `build_conversation_agent()`;checkpointer 进 `AsyncExitStack`,随 `Container.shutdown()` 逆序关闭。
- `Container.agent_service` 字段类型不变(application 端口),实现换为包装单图的 `LangChainAgentService`。

## 9. 错误处理

| 故障 | 行为 |
|---|---|
| 意图识别失败/超时 | middleware 内兜底 `general`,对话不中断 |
| 图执行中途异常 | LangGraph 失败超步不提交 checkpoint,同 thread 重发安全;`run` 抛出→路由层 500,`stream` 发 `error` 帧(现有行为) |
| 审计落库失败 | 500 + error 日志,接受记忆/审计短暂漂移(§6.2) |
| Postgres checkpointer 不可达 | 启动期:`setup()` 失败即启动失败(快速暴露);运行期:该轮 500,**不静默降级为无记忆**——宁可报错也不给"失忆的成功回复" |

## 10. 测试策略(unittest,不依赖真 Postgres)

- **RoutingMiddleware 单测**:假 recognizer + 真 `RoutingPolicy`,验证决策写 state、异常兜底、`awrap_model_call` 按技能换 prompt;
- **图级集成(核心新增)**:`MemorySaver` 替身(同为 `BaseCheckpointSaver` 接口)+ FakeChatModel 捕获请求,跑两轮对话,断言第二轮模型请求携带第一轮上下文——"记忆生效"的直接证据;另挂测试中间件断言 `context_middleware` 插槽顺位生效;
- **压缩验证**:`SummarizationMiddleware` 配小阈值,断言旧轮被摘要替换且后续轮次复用;
- **用例测改造**:断言只喂最新一条、`thread_id = 会话 id`、`get_head` 不载历史;
- **仓储测**:`get_head` 只取头、原 `get`/`load_full` 行为不回归;
- **诚实边界**:`AsyncPostgresSaver` 本体与 `setup()` 建表不在单测覆盖(无 Postgres),留联调冒烟。

## 11. 非目标(YAGNI)与演进预留

**非目标**:自研压缩策略的具体实现、跨会话长期记忆(Store/langmem)、checkpoint TTL/归档、outbox/对账、`/conversations/messages` 流式版、LangGraph Studio 可视化。

**演进预留**:技能异构时单独拆子图(N2 备选路径);工具接入后 `wrap_model_call` 换工具子集 + 启用 `ContextEditingMiddleware`;Trace 可观测性采集(2026-07-20 设计)不受影响——`AgentService` 端口未变,其"装饰器包裹端口实现"的采集方案照旧成立(包裹对象由 `RoutingAgentService` 换为新的 `LangChainAgentService`),`routing` span 数据源改为图状态里的路由通道,亦可直接在 middleware 钩子处埋点;`conversation_id` 弱引用关系不变。
