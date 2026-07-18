# 对话(Conversation)子域设计

- 日期:2026-07-19
- 状态:待评审
- 关联上下文:AI 账票服务(DDD),已有 `AgentEntity` 聚合与 LangChain/LangGraph ReAct Agent

## 1. 背景与目标

系统已有 `AgentEntity`(Agent 的**定义/配置**:身份、技能、工具、提示词渲染),但**没有任何"对话"的领域模型**。当前对话状态只存在于两处:

1. `application/dto/agent_dto.py` 的 `AgentRequest.messages` —— 请求级临时 DTO,不留存;
2. LangGraph 的 `thread_id` + `MemorySaver` checkpointer(`infrastructure/ai/agent_factory.py`,默认 `enable_memory=True`)—— 多轮记忆的实际存储,进程内内存,**重启即失、无法查询、无法审计、无法发领域事件**。

目标:把"对话"提升为一等领域概念,同时满足三类诉求(均由用户确认需要):

- **多轮上下文记忆**:Agent 能记住上文、续聊;
- **持久化 + 查询审计**:对话是业务资产,可落库、查历史、归档、留痕(谁在何时说了什么);
- **驱动业务**:对话可与账票业务(收票/稽核)协作。

## 2. 关键决策(已与用户确认)

| # | 决策 | 结论 | 理由 |
|---|---|---|---|
| D1 | 对话是否建为领域聚合 | **是,建 `Conversation` 聚合** | 「审计留痕」与「驱动业务」LangGraph 的黑盒 checkpointer 给不了;也不能塞进 `AgentEntity`(生命周期与基数完全不同,一个 Agent 服务成千上万次对话) |
| D2 | 对话归属哪个上下文 | **独立「AI 对话」子域** | 用户先与 Agent 自由对话,业务产出(发票/稽核结论)是对话的**后果**而非前提;对话可复用、耦合最低;经领域事件与账票交互 |
| D3 | 对话历史的真相源 | **领域拥有,LangGraph 无状态** | 唯一真相源在 `Conversation` 聚合;审计/事件最干净。LangGraph 退化为"喂 messages → 回 reply"的无状态执行器 |

### 本设计自行拍板的默认(评审可推翻)

| # | 决策 | 默认 | 备选 / 升级路径 |
|---|---|---|---|
| D4 | `Message` 是值对象还是实体 | **不可变值对象(VO)** | 聊天记录只追加不修改,整条有序日志即审计记录,单条消息无需独立身份。将来若需"引用某一条消息"(如稽核结论引用某句),升级为聚合内**本地实体** |
| D5 | 聚合根用 pydantic 还是普通类 | **普通类** | `Conversation` 需累积领域事件、管理封装的 append-only 集合,与 pydantic 的模型语义相冲;VO 仍用 pydantic frozen(与现有 VO 一致) |
| D6 | 本 spec 范围 | **只做对话子域本身 + 事件发出侧** | 账票模块的**事件订阅侧**、以及**工具↔业务的接线**切到后续 spec(见 §11) |
| D7 | 统一语言命名 | `Conversation` / `Message` / `SendMessageUseCase` | —— |

## 3. 范围

**In scope**
- `Conversation` 聚合、`Message` 等值对象、领域事件、`ConversationRepository` 端口(domain);
- `SendMessageUseCase` 用例编排、命令/DTO(application);
- 仓储的 SQLAlchemy 实现、最小进程内事件发布器(infrastructure);
- FastAPI 对话路由(interfaces);
- 将 ReAct Agent 切为无状态(`enable_memory=False`)的装配改动。

**Out of scope(见 §11 后续)**
- 收票/稽核对**对话事件的订阅**与业务反应;
- 工具(Tool)在回合内触达账票业务的具体接线;
- 对话摘要/标题生成、按 token 预算的高级窗口裁剪;
- 鉴权/多租户/对话归属用户(owner)建模。

## 4. 架构总览:新增「对话」子域,横切四层

对话自成子域,在每层新增 `conversation/` 子包(与将来 `receiving/`、`auditing/` 的落地方式一致):

```
domain/conversation/         聚合、值对象、领域事件、仓储端口
application/conversation/     用例编排(SendMessageUseCase)、命令/DTO
infrastructure/conversation/  仓储实现(SQLAlchemy)、事件发布器实现
interfaces/conversation/      FastAPI 路由
```

依赖方向不变:`interfaces → application → domain ← infrastructure`。对话子域内部只用 `AgentId` 引用 Agent,**不 import `AgentEntity` 内部**。

### 核心闭环(每轮一次请求)

```
路由 → SendMessageUseCase.execute(cmd)
   1. repo.get(convId, window=N)               取回对话(无则 Conversation.start)
   2. convo.post_user_message(content)          ← 领域:追加用户消息(校验 ACTIVE)
   3. history = window.select(convo.messages)   ← 领域策略:裁剪上下文窗口
   4. agent.run(AgentRequest(messages=history)) ← LangGraph 无状态执行
   5. convo.record_assistant_message(reply)     ← 领域:追加助手回复
   6. repo.save(convo)                          只 append 新消息
   7. publisher.publish(convo.pull_events())    发布领域事件
```

真相源只有一处:`Conversation` 聚合。

## 5. 领域模型(domain/conversation/)

> 以下为**设计示意**,非最终实现;命名与签名以此为准,细节实现时可微调。

### 5.1 值对象

```python
class ConversationId(BaseModel):      # frozen
    value: str                         # uuid4 hex

class MessageRole(str, Enum):
    USER = "user"; ASSISTANT = "assistant"; SYSTEM = "system"; TOOL = "tool"

class ToolCallRecord(BaseModel):      # frozen —— 审计用,MVP 可留空
    tool_name: str
    args_summary: str = ""
    result_summary: str = ""

class Message(BaseModel):             # frozen —— 一旦产生不可改(审计完整性)
    role: MessageRole
    content: str
    created_at: datetime
    tool_calls: tuple[ToolCallRecord, ...] = ()

class ConversationStatus(str, Enum):
    ACTIVE = "active"; CLOSED = "closed"
```

### 5.2 聚合根 `Conversation`(普通类)

```python
class Conversation:
    id: ConversationId
    agent_id: AgentId                 # 仅引用,不内嵌
    status: ConversationStatus
    created_at: datetime
    updated_at: datetime
    # 内部封装
    _messages: list[Message]          # 有序、只追加
    _events:   list[DomainEvent]      # 待发布领域事件
    _pending:  list[Message]          # 本次会话新追加、待落库的消息

    @classmethod
    def start(cls, agent_id: AgentId) -> "Conversation":
        """新建对话,生成 id,发 ConversationStarted。"""

    def post_user_message(self, content: str) -> Message:
        """追加用户消息。不变量:status == ACTIVE 才能追加。"""

    def record_assistant_message(
        self, content: str, tool_calls: tuple[ToolCallRecord, ...] = ()
    ) -> Message:
        """追加助手回复。发 AssistantResponded。"""

    def close(self) -> None:
        """关闭对话。发 ConversationClosed。"""

    @property
    def messages(self) -> tuple[Message, ...]:
        """只读视图。"""

    def pull_events(self) -> list[DomainEvent]:
        """应用层保存后取走并发布,清空内部列表。"""

    def pull_new_messages(self) -> list[Message]:
        """仓储只落这些 append 的新消息,清空 _pending。"""
```

### 5.3 不变量(全部在聚合根,均无需加载全量历史)

1. `CLOSED` 后不能再 `post_user_message` / `record_assistant_message`(违反抛领域异常);
2. 消息只追加、不修改、不删除,`_messages` 顺序即时序;
3. `created_at` 单调不减。

> 这三条只依赖对话头(`status`)与"追加到末尾",**不需要全量历史即可校验**——这是 §7 仓储做窗口加载/增量落库的前提。

### 5.4 领域事件

```python
@dataclass(frozen=True)
class DomainEvent:                    # 放 domain/shared/events.py
    occurred_at: datetime

@dataclass(frozen=True)
class ConversationStarted(DomainEvent):
    conversation_id: str
    agent_id: str

@dataclass(frozen=True)
class AssistantResponded(DomainEvent):
    conversation_id: str
    content: str
    tool_calls: tuple[ToolCallRecord, ...] = ()

@dataclass(frozen=True)
class ConversationClosed(DomainEvent):
    conversation_id: str
```

## 6. 上下文窗口策略(领域策略,可插拔)

```python
# domain/conversation/context_window.py
class ContextWindowPolicy:
    size: int = 20
    def select(self, messages: tuple[Message, ...]) -> list[Message]:
        """默认:返回最近 size 条。"""
```

放 domain,因为"给 Agent 看多少上下文"是**领域决策**而非技术细节。MVP 用"最近 N 条";按 token 预算裁剪、"保留首条系统消息 + 最近若干轮"等为后续增强。

## 7. 仓储端口与持久化

### 7.1 端口(domain)

```python
# domain/conversation/repository.py
class ConversationRepository(ABC):
    async def get(self, cid: ConversationId, *, window: int | None = None) -> Conversation | None:
        """聊天闭环用:加载对话头 + 最近 window 条消息(None 表示全量)。"""
    async def save(self, convo: Conversation) -> None:
        """upsert 对话头 + 只 INSERT pull_new_messages() 的新消息,不重写历史。"""
    async def load_full(self, cid: ConversationId) -> Conversation | None:
        """审计/查询用:全量加载。"""
```

### 7.2 聚合体量处理(重要)

长对话可能上千条消息,**绝不能每轮把全部消息灌进聚合**:

- **聊天闭环**:`get(window=N)` 只取对话头 + 最近 N 条(够喂 LLM);`save` 只 INSERT 新增消息。
- **审计/查询**:走 `load_full` 或独立读模型(CQRS 读侧),与写路径分离。

### 7.3 实现(infrastructure,SQLAlchemy 2.0)

两张表:

- `conversation(id, agent_name, agent_version, status, created_at, updated_at)`
- `conversation_message(id, conversation_id FK, seq, role, content, tool_calls JSON, created_at)`,`(conversation_id, seq)` 唯一。

仓储做**显式映射**(领域对象 ↔ ORM 行),不把聚合直接 `model_dump` 落库。

## 8. 应用层用例(application/conversation/)

```python
@dataclass
class SendMessageCommand:
    content: str
    agent_id: AgentId
    conversation_id: str | None = None   # 空 = 新开对话

@dataclass
class ChatResult:
    conversation_id: str
    reply: str

class SendMessageUseCase:
    def __init__(self, repo: ConversationRepository, agent: AgentService,
                 publisher: DomainEventPublisher, window: ContextWindowPolicy): ...

    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        convo = (await self._repo.get(ConversationId(value=cmd.conversation_id), window=self._window.size)
                 if cmd.conversation_id else None) or Conversation.start(cmd.agent_id)

        convo.post_user_message(cmd.content)                       # 领域
        history = self._window.select(convo.messages)              # 领域策略
        request = AgentRequest(
            messages=[{"role": m.role.value, "content": m.content} for m in history],
            thread_id=convo.id.value,   # 仅用于链路追踪,不再驱动记忆
        )
        response = await self._agent.run(request)                  # LangGraph 无状态
        convo.record_assistant_message(response.reply)             # 领域

        await self._repo.save(convo)
        for ev in convo.pull_events():
            await self._publisher.publish(ev)
        return ChatResult(conversation_id=convo.id.value, reply=response.reply)
```

用例**只编排**:取聚合 → 调领域方法 → 经 Agent 端口执行 → 保存 → 发事件。业务规则(不变量、窗口策略)全在 domain。

`DomainEventPublisher` 为 application 层端口(`async publish(event) -> None`),infrastructure 提供最小进程内实现;订阅者以后再挂(§11)。

## 9. 与现有代码的衔接(改动很小)

| 现有 | 改动 |
|---|---|
| `agent_factory.create_react_agent` | 装配时传 `enable_memory=False`(或 `checkpointer=None`)——**这是"无状态"的唯一开关** |
| `LangChainAgentService`(`interfaces/ai/react_agent.py`) | **不改**:它本就是"喂 messages → 回 reply",天然支持无状态 |
| `AgentRequest.thread_id` | 语义降级为"链路追踪 id",不再驱动记忆(记忆改由 domain 提供 messages) |
| `AgentResponse` | MVP 不改;后续可补结构化 `tool_calls` 字段,好让 `record_assistant_message` 留痕(见 §11) |
| `bootstrap`(container/dependencies) | 装配 `ConversationRepository` 实现、`DomainEventPublisher`、`SendMessageUseCase`;Agent 记忆关掉 |

## 10. 领域事件与"驱动业务"的边界

`Conversation` 只发**事实事件**(`ConversationStarted` / `AssistantResponded` / `ConversationClosed`)。收票/稽核以后**订阅**这些事件——符合"跨模块只经领域事件"的铁律。

需明确一个 agent 系统的现实:**"对话中确认 → 生成稽核结论"这类实时动作,主力机制是"工具(Tool)"而非事件**。因此整合有两条路,均在后续 spec 展开:

- **工具**:回合内 Agent 调用领域工具 → 该工具(在 infra)**只能经应用端口/发命令**去触达账票,不得直接 import 收票/稽核模块;
- **领域事件**:回合结束后的松耦合反应(归档、留痕、通知)。

## 11. 后续(独立 spec)

1. **账票订阅侧**:收票/稽核如何订阅对话事件并作出业务反应;
2. **工具↔业务接线**:回合内工具经端口/命令触达账票的具体设计;
3. **`AgentResponse` 结构化工具调用**:把工具调用明细回传,写入 `Message.tool_calls`;
4. **高级窗口/摘要**:按 token 预算裁剪、长对话滚动摘要;
5. **对话归属**:owner/租户、鉴权;
6. **前置修复**:主干里 `bootstrap` 引用了不存在的 `infrastructure.config.nacos_client.NacosConfigClient`,与真实的 `infrastructure/client/nacos.py::NacosClient` 是两套名字——需先理顺才能整体跑通(与本 spec 独立,但会阻塞联调)。

## 12. 测试策略(unittest,零依赖)

- **领域纯单测**:`CLOSED` 后追加消息抛领域异常;追加顺序与 `created_at` 单调;`start`/`record_assistant_message`/`close` 各自产出正确领域事件;`pull_events`/`pull_new_messages` 取走后清空。
- **用例测**:用 in-memory 假 `ConversationRepository` + 假 `AgentService` + 假 `DomainEventPublisher`,验证闭环调用顺序、无状态请求携带的 history 内容正确、事件被发布。
- **仓储测**:`save` 只 append 新消息(不重写历史);`get(window=N)` 只取最近 N 条;`load_full` 取全量;`(conversation_id, seq)` 唯一约束生效。
