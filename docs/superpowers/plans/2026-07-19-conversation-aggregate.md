# 对话（Conversation）子域 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把「对话」提升为一等领域概念：新增 `Conversation` 聚合（真相源）、`Message` 等值对象、领域事件、`ConversationRepository` 端口与 SQLAlchemy 实现、`SendMessageUseCase` 用例、FastAPI 对话路由，并把 ReAct Agent 切为无状态（记忆由领域提供 history）。

**Architecture:** 对话自成子域，在每层新增 `conversation/` 子包（`domain/application/infrastructure/interfaces`）。每轮闭环：路由 → `SendMessageUseCase.execute` →（取聚合/新开 → 追加用户消息 → 领域策略裁剪窗口 → LangGraph 无状态执行 → 追加助手回复 → 只 append 落库 → 发领域事件）。唯一真相源是 `Conversation` 聚合；LangGraph 退化为「喂 messages → 回 reply」的无状态执行器。

**Tech Stack:** Pydantic v2、SQLAlchemy 2.0（async / asyncpg，测试用 aiosqlite）、greenlet、unittest（异步用 `asyncio.run`）。

**对应设计:** [docs/superpowers/specs/2026-07-19-conversation-aggregate-design.md](../specs/2026-07-19-conversation-aggregate-design.md)

**与其它计划的关系:** 本计划把多轮记忆从 LangGraph `MemorySaver` 迁入 `Conversation` 聚合并**关闭** Agent 记忆（`enable_memory=False`）。若已实施 [SSE 计划](2026-07-19-agent-sse-streaming.md)，其「单例保住 `thread_id` 记忆」的动机被本子域取代——记忆改由聚合经 history 提供，`thread_id` 降级为链路追踪 id。本计划与 SSE/路由计划的代码基本正交（只在 bootstrap 交汇），可独立实现。

## Global Constraints

以下为全项目硬约束，每个任务都隐含遵守：

- **Python 3.11，一律 `uv run`**。
- **Pydantic v2 建模，禁止 `dataclasses.dataclass`（CLAUDE.md 规则 11 + 用户记忆强约束）**。
  → 设计文档 §5.4/§8 用 `@dataclass(frozen=True)` 定义领域事件与命令/结果，**本计划一律改用 Pydantic v2 frozen `BaseModel`**（Pydantic 关键字构造，天然规避「默认字段后接必填字段」的排序限制，转换更干净）。
- **聚合根用 Pydantic（偏离设计 §5.2 的「普通类」决策 D5）**：本仓库既有聚合根 [`AgentEntity`](../../../src/domain/entities/agent_entity.py) 就是「带变更方法的 Pydantic 模型」。为与既有约定一致并满足规则 11，`Conversation` 用 Pydantic `BaseModel` + `PrivateAttr` 承载封装的 append-only 集合与待发布事件——设计 D5 顾虑的「与 pydantic 语义冲突」被 `AgentEntity` 先例证否。**评审可推翻此偏离**。
- **中文**：对话、注释、文档、Git 提交信息一律中文。
- **DDD 依赖方向**：`interfaces → application → domain ← infrastructure`；`domain` 不 import 任何框架（SQLAlchemy/FastAPI 等）。对话子域内部只用 `AgentId` 引用 Agent，不 import `AgentEntity` 内部行为。
- **测试用标准库 `unittest`（零依赖）**，异步用 `asyncio.run(...)`；仓储测试用内存 SQLite（`aiosqlite` + `StaticPool`）。
- **提交信息尾行**：
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/domain/shared/events.py` | `DomainEvent` 基类（Pydantic frozen，`occurred_at`） | 创建 |
| `src/domain/conversation/__init__.py` | 对话领域子包标记 | 创建 |
| `src/domain/conversation/value_objects.py` | `ConversationId/MessageRole/ToolCallRecord/Message/ConversationStatus` | 创建 |
| `src/domain/conversation/events.py` | `ConversationStarted/AssistantResponded/ConversationClosed` | 创建 |
| `src/domain/conversation/aggregate.py` | `Conversation` 聚合根 + `ConversationClosedError` | 创建 |
| `src/domain/conversation/context_window.py` | `ContextWindowPolicy` 上下文窗口策略 | 创建 |
| `src/domain/conversation/repository.py` | `ConversationRepository` 端口（ABC） | 创建 |
| `src/application/ports/event_publisher.py` | `DomainEventPublisher` 端口（Protocol） | 创建 |
| `src/application/conversation/__init__.py` | 对话应用子包标记 | 创建 |
| `src/application/conversation/commands.py` | `SendMessageCommand` / `ChatResult`（Pydantic） | 创建 |
| `src/application/conversation/send_message.py` | `SendMessageUseCase` 用例编排 | 创建 |
| `src/infrastructure/conversation/__init__.py` | 对话基础设施子包标记 | 创建 |
| `src/infrastructure/conversation/models.py` | SQLAlchemy ORM 模型 + 建表助手 | 创建 |
| `src/infrastructure/conversation/repository.py` | `SqlAlchemyConversationRepository` + 显式映射 | 创建 |
| `src/infrastructure/conversation/event_publisher.py` | `InMemoryEventPublisher` 进程内发布器 | 创建 |
| `src/interfaces/conversation/__init__.py` | 对话接口子包标记 | 创建 |
| `src/interfaces/conversation/schemas.py` | `SendMessageBody` / `ChatResultResponse` | 创建 |
| `src/interfaces/conversation/router.py` | `POST /conversations/messages` | 创建 |
| `src/bootstrap/container.py` | Agent 记忆关闭 + `build_conversation_use_case` 装配 | 修改 |
| `src/bootstrap/dependencies.py` | `get_send_message_use_case` DI | 修改 |
| `src/bootstrap/main.py` | lifespan 建表 + 装配用例 + `include_router` | 修改 |
| `pyproject.toml` | `greenlet`（运行时）、`aiosqlite`（dev） | 修改（经 `uv add`） |
| `tests/test_*.py` | 各任务测试（见每个 Task） | 创建 |

---

## Task 1: DomainEvent 基类

领域事件基类，放 `domain/shared/events.py`。Pydantic frozen，携带 `occurred_at`。设计 §5.4 用 dataclass，本计划改 Pydantic。

**Files:**
- Create: `src/domain/shared/events.py`
- Test: `tests/test_domain_event.py`

**Interfaces:**
- Produces: `DomainEvent(occurred_at: datetime = <now UTC>)` frozen Pydantic 基类，供各子域事件继承。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_domain_event.py`：

```python
"""DomainEvent 基类测试——frozen 且自带 occurred_at。"""
from __future__ import annotations

import unittest
from datetime import datetime

from pydantic import ValidationError

from domain.shared.events import DomainEvent


class DomainEventTest(unittest.TestCase):
    def test_has_occurred_at(self) -> None:
        self.assertIsInstance(DomainEvent().occurred_at, datetime)

    def test_frozen(self) -> None:
        ev = DomainEvent()
        with self.assertRaises(ValidationError):
            ev.occurred_at = datetime.now()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_domain_event -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.shared.events'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/shared/events.py`：

```python
"""领域事件基类 —— 聚合内产生的「已发生的事实」，跨模块解耦只经领域事件。"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """所有领域事件的基类（不可变）。"""

    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_domain_event -v`
Expected: PASS（2 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/shared/events.py tests/test_domain_event.py
git commit -m "feat: 新增 DomainEvent 领域事件基类（Pydantic frozen）"
```

---

## Task 2: 对话值对象

`ConversationId`、`MessageRole`、`ToolCallRecord`、`Message`、`ConversationStatus`。`Message` frozen，一旦产生不可改（审计完整性）。

**Files:**
- Create: `src/domain/conversation/__init__.py`
- Create: `src/domain/conversation/value_objects.py`
- Test: `tests/test_conversation_value_objects.py`

**Interfaces:**
- Produces:
  - `ConversationId(value: str)` frozen
  - `MessageRole(str, Enum)`：`USER/ASSISTANT/SYSTEM/TOOL`
  - `ConversationStatus(str, Enum)`：`ACTIVE/CLOSED`
  - `ToolCallRecord(tool_name: str, args_summary: str="", result_summary: str="")` frozen
  - `Message(role: MessageRole, content: str, created_at: datetime, tool_calls: tuple[ToolCallRecord, ...]=())` frozen

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_value_objects.py`：

```python
"""对话值对象测试——枚举、frozen Message、ToolCallRecord。"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
    ToolCallRecord,
)


class ValueObjectsTest(unittest.TestCase):
    def test_conversation_id(self) -> None:
        self.assertEqual(ConversationId(value="abc").value, "abc")

    def test_roles(self) -> None:
        self.assertEqual(MessageRole.USER.value, "user")
        self.assertEqual(ConversationStatus.CLOSED.value, "closed")

    def test_message_frozen(self) -> None:
        msg = Message(role=MessageRole.USER, content="你好", created_at=datetime.now(timezone.utc))
        self.assertEqual(msg.tool_calls, ())
        with self.assertRaises(ValidationError):
            msg.content = "改不了"  # type: ignore[misc]

    def test_message_with_tool_calls(self) -> None:
        tc = ToolCallRecord(tool_name="lookup_invoice", args_summary="INV-001")
        msg = Message(
            role=MessageRole.ASSISTANT, content="查到了",
            created_at=datetime.now(timezone.utc), tool_calls=(tc,),
        )
        self.assertEqual(msg.tool_calls[0].tool_name, "lookup_invoice")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_value_objects -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.conversation'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/conversation/__init__.py`：

```python
"""对话（Conversation）领域子域 —— 聚合、值对象、领域事件、仓储端口。"""
```

创建 `src/domain/conversation/value_objects.py`：

```python
"""对话子域值对象（不可变，零框架依赖）。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ConversationId(BaseModel):
    """对话标识（uuid4 hex）。"""

    value: str
    model_config = {"frozen": True}


class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"


class ToolCallRecord(BaseModel):
    """工具调用留痕（审计用，MVP 可留空）。"""

    tool_name: str
    args_summary: str = ""
    result_summary: str = ""
    model_config = {"frozen": True}


class Message(BaseModel):
    """一条对话消息——一旦产生不可改（审计完整性）。"""

    role: MessageRole
    content: str
    created_at: datetime
    tool_calls: tuple[ToolCallRecord, ...] = Field(default=())
    model_config = {"frozen": True}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_value_objects -v`
Expected: PASS（4 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/conversation/__init__.py src/domain/conversation/value_objects.py tests/test_conversation_value_objects.py
git commit -m "feat: 新增对话子域值对象（ConversationId/Message/ToolCallRecord 等）"
```

---

## Task 3: 对话领域事件

`ConversationStarted`、`AssistantResponded`、`ConversationClosed`，继承 `DomainEvent`。设计用 dataclass，本计划改 Pydantic。

**Files:**
- Create: `src/domain/conversation/events.py`
- Test: `tests/test_conversation_events.py`

**Interfaces:**
- Consumes: `DomainEvent`（Task 1）、`ToolCallRecord`（Task 2）。
- Produces:
  - `ConversationStarted(conversation_id: str, agent_id: str)`
  - `AssistantResponded(conversation_id: str, content: str, tool_calls: tuple[ToolCallRecord, ...]=())`
  - `ConversationClosed(conversation_id: str)`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_events.py`：

```python
"""对话领域事件测试——字段与继承 occurred_at。"""
from __future__ import annotations

import unittest
from datetime import datetime

from domain.conversation.events import (
    AssistantResponded,
    ConversationClosed,
    ConversationStarted,
)
from domain.shared.events import DomainEvent


class ConversationEventsTest(unittest.TestCase):
    def test_started(self) -> None:
        ev = ConversationStarted(conversation_id="c1", agent_id="default_agent:default")
        self.assertIsInstance(ev, DomainEvent)
        self.assertEqual(ev.conversation_id, "c1")
        self.assertIsInstance(ev.occurred_at, datetime)

    def test_assistant_responded_default_tool_calls(self) -> None:
        ev = AssistantResponded(conversation_id="c1", content="答复")
        self.assertEqual(ev.tool_calls, ())

    def test_closed(self) -> None:
        self.assertEqual(ConversationClosed(conversation_id="c1").conversation_id, "c1")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_events -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.conversation.events'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/conversation/events.py`：

```python
"""对话子域领域事件 —— 只表达「已发生的事实」。"""
from __future__ import annotations

from domain.conversation.value_objects import ToolCallRecord
from domain.shared.events import DomainEvent


class ConversationStarted(DomainEvent):
    conversation_id: str
    agent_id: str


class AssistantResponded(DomainEvent):
    conversation_id: str
    content: str
    tool_calls: tuple[ToolCallRecord, ...] = ()


class ConversationClosed(DomainEvent):
    conversation_id: str
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_events -v`
Expected: PASS（3 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/conversation/events.py tests/test_conversation_events.py
git commit -m "feat: 新增对话领域事件（ConversationStarted/AssistantResponded/ConversationClosed）"
```

---

## Task 4: Conversation 聚合根

聚合根是一致性与事务边界。Pydantic 模型 + `PrivateAttr` 承载 append-only 的 `_messages`、待发布 `_events`、待落库 `_pending`。不变量全在聚合，且只依赖对话头 + 末尾追加，无需加载全量历史。

**Files:**
- Create: `src/domain/conversation/aggregate.py`
- Test: `tests/test_conversation_aggregate.py`

**Interfaces:**
- Consumes: `AgentId`（`domain.entities.agent_entity`）、Task 2 值对象、Task 3 事件、`DomainEvent`。
- Produces:
  - `ConversationClosedError(Exception)`
  - `Conversation`（Pydantic）字段：`id: ConversationId`、`agent_id: AgentId`、`status: ConversationStatus`、`created_at/updated_at: datetime`
  - 类方法 `start(agent_id: AgentId) -> Conversation`
  - 类方法 `reconstitute(*, id, agent_id, status, created_at, updated_at, messages: list[Message]) -> Conversation`（仓储重建用，不发事件、不入 pending）
  - `post_user_message(content: str) -> Message`
  - `record_assistant_message(content: str, tool_calls: tuple[ToolCallRecord, ...]=()) -> Message`
  - `close() -> None`
  - `property messages -> tuple[Message, ...]`（只读视图）
  - `pull_events() -> list[DomainEvent]`（取走并清空）
  - `pull_new_messages() -> list[Message]`（取走并清空 `_pending`）

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_aggregate.py`：

```python
"""Conversation 聚合根测试——不变量、事件、pull 语义、重建。"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from domain.conversation.aggregate import Conversation, ConversationClosedError
from domain.conversation.events import (
    AssistantResponded,
    ConversationClosed,
    ConversationStarted,
)
from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
)
from domain.entities.agent_entity import AgentId


def _agent() -> AgentId:
    return AgentId(name="default_agent", version="default")


class ConversationAggregateTest(unittest.TestCase):
    def test_start_emits_started_event(self) -> None:
        convo = Conversation.start(_agent())
        self.assertEqual(convo.status, ConversationStatus.ACTIVE)
        events = convo.pull_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ConversationStarted)
        self.assertEqual(convo.pull_events(), [])  # 取走后清空

    def test_post_and_record_append_in_order(self) -> None:
        convo = Conversation.start(_agent())
        convo.post_user_message("查发票 12345")
        convo.record_assistant_message("税额 13 元")
        roles = [m.role for m in convo.messages]
        self.assertEqual(roles, [MessageRole.USER, MessageRole.ASSISTANT])

    def test_record_emits_assistant_responded(self) -> None:
        convo = Conversation.start(_agent())
        convo.pull_events()  # 清掉 started
        convo.record_assistant_message("答复")
        events = convo.pull_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AssistantResponded)

    def test_closed_rejects_new_messages(self) -> None:
        convo = Conversation.start(_agent())
        convo.close()
        with self.assertRaises(ConversationClosedError):
            convo.post_user_message("还能说话吗")

    def test_close_emits_closed_event(self) -> None:
        convo = Conversation.start(_agent())
        convo.pull_events()
        convo.close()
        self.assertIsInstance(convo.pull_events()[0], ConversationClosed)

    def test_pull_new_messages_returns_and_clears(self) -> None:
        convo = Conversation.start(_agent())
        convo.post_user_message("a")
        convo.record_assistant_message("b")
        pending = convo.pull_new_messages()
        self.assertEqual(len(pending), 2)
        self.assertEqual(convo.pull_new_messages(), [])

    def test_reconstitute_no_events_no_pending(self) -> None:
        msgs = [Message(role=MessageRole.USER, content="旧消息", created_at=datetime.now(timezone.utc))]
        convo = Conversation.reconstitute(
            id=ConversationId(value="c1"), agent_id=_agent(),
            status=ConversationStatus.ACTIVE,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
            messages=msgs,
        )
        self.assertEqual(len(convo.messages), 1)
        self.assertEqual(convo.pull_events(), [])       # 重建不发事件
        self.assertEqual(convo.pull_new_messages(), [])  # 重建不入 pending


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_aggregate -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.conversation.aggregate'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/conversation/aggregate.py`：

```python
"""Conversation 聚合根 —— 对话历史的唯一真相源。

以 Pydantic 模型 + PrivateAttr 承载封装的 append-only 集合与待发布事件
（与既有聚合根 AgentEntity 的建模方式一致）。不变量只依赖对话头与末尾
追加，无需加载全量历史——这是仓储做窗口加载/增量落库的前提。
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, PrivateAttr

from domain.conversation.events import (
    AssistantResponded,
    ConversationClosed,
    ConversationStarted,
)
from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
    ToolCallRecord,
)
from domain.entities.agent_entity import AgentId
from domain.shared.events import DomainEvent


class ConversationClosedError(Exception):
    """对话已关闭后仍试图追加消息。"""


class Conversation(BaseModel):
    """AI 对话聚合根。"""

    id: ConversationId
    agent_id: AgentId
    status: ConversationStatus = ConversationStatus.ACTIVE
    created_at: datetime
    updated_at: datetime

    _messages: list[Message] = PrivateAttr(default_factory=list)  # 有序、只追加
    _events: list[DomainEvent] = PrivateAttr(default_factory=list)  # 待发布领域事件
    _pending: list[Message] = PrivateAttr(default_factory=list)  # 待落库的新消息

    # ── 工厂 ──────────────────────────────────────────────

    @classmethod
    def start(cls, agent_id: AgentId) -> "Conversation":
        """新建对话，生成 id，发 ConversationStarted。"""
        now = datetime.now(timezone.utc)
        convo = cls(
            id=ConversationId(value=uuid4().hex),
            agent_id=agent_id,
            status=ConversationStatus.ACTIVE,
            created_at=now,
            updated_at=now,
        )
        convo._events.append(
            ConversationStarted(conversation_id=convo.id.value, agent_id=str(agent_id))
        )
        return convo

    @classmethod
    def reconstitute(
        cls,
        *,
        id: ConversationId,
        agent_id: AgentId,
        status: ConversationStatus,
        created_at: datetime,
        updated_at: datetime,
        messages: list[Message],
    ) -> "Conversation":
        """仓储重建：装入历史消息，不发事件、不入 pending。"""
        convo = cls(
            id=id, agent_id=agent_id, status=status,
            created_at=created_at, updated_at=updated_at,
        )
        convo._messages = list(messages)
        return convo

    # ── 领域行为 ──────────────────────────────────────────

    def post_user_message(self, content: str) -> Message:
        """追加用户消息。不变量：status == ACTIVE 才能追加。"""
        self._ensure_active()
        msg = Message(role=MessageRole.USER, content=content, created_at=self._now())
        self._append(msg)
        return msg

    def record_assistant_message(
        self, content: str, tool_calls: tuple[ToolCallRecord, ...] = ()
    ) -> Message:
        """追加助手回复，发 AssistantResponded。"""
        self._ensure_active()
        msg = Message(
            role=MessageRole.ASSISTANT, content=content,
            created_at=self._now(), tool_calls=tuple(tool_calls),
        )
        self._append(msg)
        self._events.append(
            AssistantResponded(
                conversation_id=self.id.value, content=content, tool_calls=tuple(tool_calls)
            )
        )
        return msg

    def close(self) -> None:
        """关闭对话（幂等），发 ConversationClosed。"""
        if self.status is ConversationStatus.CLOSED:
            return
        self.status = ConversationStatus.CLOSED
        self.updated_at = self._now()
        self._events.append(ConversationClosed(conversation_id=self.id.value))

    # ── 只读视图 / 取走语义 ─────────────────────────────────

    @property
    def messages(self) -> tuple[Message, ...]:
        return tuple(self._messages)

    def pull_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def pull_new_messages(self) -> list[Message]:
        pending = list(self._pending)
        self._pending.clear()
        return pending

    # ── 内部 ──────────────────────────────────────────────

    def _append(self, msg: Message) -> None:
        self._messages.append(msg)
        self._pending.append(msg)
        self.updated_at = msg.created_at

    def _ensure_active(self) -> None:
        if self.status is not ConversationStatus.ACTIVE:
            raise ConversationClosedError("对话已关闭，不能再追加消息")

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_aggregate -v`
Expected: PASS（7 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/conversation/aggregate.py tests/test_conversation_aggregate.py
git commit -m "feat: 新增 Conversation 聚合根（Pydantic + PrivateAttr，append-only + 领域事件）"
```

---

## Task 5: 上下文窗口策略

「给 Agent 看多少上下文」是领域决策。MVP：返回最近 `size` 条。

**Files:**
- Create: `src/domain/conversation/context_window.py`
- Test: `tests/test_context_window.py`

**Interfaces:**
- Consumes: `Message`（Task 2）。
- Produces: `ContextWindowPolicy(size: int = 20)`；`select(messages: tuple[Message, ...]) -> list[Message]`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_context_window.py`：

```python
"""ContextWindowPolicy 测试——最近 N 条裁剪。"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from domain.conversation.context_window import ContextWindowPolicy
from domain.conversation.value_objects import Message, MessageRole


def _msgs(n: int) -> tuple[Message, ...]:
    now = datetime.now(timezone.utc)
    return tuple(
        Message(role=MessageRole.USER, content=str(i), created_at=now) for i in range(n)
    )


class ContextWindowPolicyTest(unittest.TestCase):
    def test_selects_last_n(self) -> None:
        selected = ContextWindowPolicy(size=3).select(_msgs(10))
        self.assertEqual([m.content for m in selected], ["7", "8", "9"])

    def test_fewer_than_size_returns_all(self) -> None:
        self.assertEqual(len(ContextWindowPolicy(size=20).select(_msgs(2))), 2)

    def test_non_positive_size_returns_all(self) -> None:
        self.assertEqual(len(ContextWindowPolicy(size=0).select(_msgs(5))), 5)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_context_window -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.conversation.context_window'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/conversation/context_window.py`：

```python
"""上下文窗口策略 —— 领域决策，可插拔。MVP 用「最近 N 条」。"""
from __future__ import annotations

from domain.conversation.value_objects import Message


class ContextWindowPolicy:
    """裁剪喂给 Agent 的上下文窗口。"""

    def __init__(self, size: int = 20) -> None:
        self.size = size

    def select(self, messages: tuple[Message, ...]) -> list[Message]:
        """默认返回最近 size 条；size<=0 时返回全部。"""
        if self.size <= 0:
            return list(messages)
        return list(messages[-self.size :])
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_context_window -v`
Expected: PASS（3 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/conversation/context_window.py tests/test_context_window.py
git commit -m "feat: 新增 ContextWindowPolicy 上下文窗口策略"
```

---

## Task 6: 仓储端口 + 事件发布端口 + 命令/结果 DTO

`ConversationRepository`（domain ABC）、`DomainEventPublisher`（application Protocol）、`SendMessageCommand`/`ChatResult`（application，Pydantic）。设计 §8 用 dataclass，本计划改 Pydantic。

**Files:**
- Create: `src/domain/conversation/repository.py`
- Create: `src/application/ports/event_publisher.py`
- Create: `src/application/conversation/__init__.py`
- Create: `src/application/conversation/commands.py`
- Test: `tests/test_conversation_commands.py`

**Interfaces:**
- Produces:
  - `ConversationRepository(ABC)`：`async get(cid: ConversationId, *, window: int | None=None) -> Conversation | None`、`async save(convo: Conversation) -> None`、`async load_full(cid: ConversationId) -> Conversation | None`
  - `DomainEventPublisher(Protocol)`：`async publish(event: DomainEvent) -> None`
  - `SendMessageCommand(content: str, agent_id: AgentId, conversation_id: str | None=None)`
  - `ChatResult(conversation_id: str, reply: str)`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_commands.py`（端口是抽象契约，此处只测命令/结果 DTO 与 ABC 不可实例化）：

```python
"""命令/结果 DTO 与仓储端口测试。"""
from __future__ import annotations

import unittest

from application.conversation.commands import ChatResult, SendMessageCommand
from domain.conversation.repository import ConversationRepository
from domain.entities.agent_entity import AgentId


class CommandsTest(unittest.TestCase):
    def test_send_message_command(self) -> None:
        cmd = SendMessageCommand(content="你好", agent_id=AgentId(name="default_agent"))
        self.assertEqual(cmd.content, "你好")
        self.assertIsNone(cmd.conversation_id)

    def test_chat_result(self) -> None:
        self.assertEqual(ChatResult(conversation_id="c1", reply="答复").reply, "答复")

    def test_repository_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            ConversationRepository()  # type: ignore[abstract]


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_commands -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'application.conversation'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/conversation/repository.py`：

```python
"""对话仓储端口（domain）。聊天闭环用窗口加载 + 增量落库；审计走全量。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.conversation.aggregate import Conversation
from domain.conversation.value_objects import ConversationId


class ConversationRepository(ABC):
    @abstractmethod
    async def get(
        self, cid: ConversationId, *, window: int | None = None
    ) -> Conversation | None:
        """加载对话头 + 最近 window 条消息（None 表示全量）。"""
        ...

    @abstractmethod
    async def save(self, convo: Conversation) -> None:
        """upsert 对话头 + 只 INSERT pull_new_messages() 的新消息，不重写历史。"""
        ...

    @abstractmethod
    async def load_full(self, cid: ConversationId) -> Conversation | None:
        """审计/查询用：全量加载。"""
        ...
```

创建 `src/application/ports/event_publisher.py`：

```python
"""领域事件发布端口（application）。infrastructure 提供进程内实现。"""
from __future__ import annotations

from typing import Protocol

from domain.shared.events import DomainEvent


class DomainEventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None:
        """发布一条领域事件给订阅者。"""
        ...
```

创建 `src/application/conversation/__init__.py`：

```python
"""对话应用子域 —— 用例编排、命令/DTO。"""
```

创建 `src/application/conversation/commands.py`：

```python
"""对话用例的命令与结果 DTO（Pydantic v2）。"""
from __future__ import annotations

from pydantic import BaseModel

from domain.entities.agent_entity import AgentId


class SendMessageCommand(BaseModel):
    content: str
    agent_id: AgentId
    conversation_id: str | None = None  # 空 = 新开对话

    model_config = {"arbitrary_types_allowed": True}


class ChatResult(BaseModel):
    conversation_id: str
    reply: str
```

> 说明：`AgentId` 本身是 Pydantic 模型，作为字段无需特殊配置；`arbitrary_types_allowed` 仅为稳妥保留，若无警告可去除。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_commands -v`
Expected: PASS（3 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/conversation/repository.py src/application/ports/event_publisher.py src/application/conversation/__init__.py src/application/conversation/commands.py tests/test_conversation_commands.py
git commit -m "feat: 新增 ConversationRepository/DomainEventPublisher 端口与命令 DTO"
```

---

## Task 7: SendMessageUseCase 用例编排

只编排：取聚合/新开 → 追加用户消息 → 领域策略裁剪窗口 → Agent 端口无状态执行 → 追加助手回复 → 保存 → 发事件。业务规则全在 domain。

**Files:**
- Create: `src/application/conversation/send_message.py`
- Test: `tests/test_send_message_use_case.py`

**Interfaces:**
- Consumes: `ConversationRepository`（Task 6）、`AgentService`（`application.ports.agent_service`）、`DomainEventPublisher`（Task 6）、`ContextWindowPolicy`（Task 5）、`SendMessageCommand/ChatResult`（Task 6）、`Conversation`（Task 4）、`ConversationId`、`AgentRequest`（`application.dto.agent_dto`）。
- Produces: `SendMessageUseCase(repo, agent, publisher, window)`；`async execute(cmd: SendMessageCommand) -> ChatResult`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_send_message_use_case.py`（全用假件，不触真实 IO/LLM）：

```python
"""SendMessageUseCase 测试——闭环顺序、history 内容、事件发布、新开/续聊。"""
from __future__ import annotations

import asyncio
import unittest

from application.conversation.commands import SendMessageCommand
from application.conversation.send_message import SendMessageUseCase
from application.dto.agent_dto import AgentRequest, AgentResponse
from domain.conversation.aggregate import Conversation
from domain.conversation.context_window import ContextWindowPolicy
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId


class _FakeRepo:
    def __init__(self) -> None:
        self.saved: dict[str, Conversation] = {}
    async def get(self, cid: ConversationId, *, window=None) -> Conversation | None:
        return self.saved.get(cid.value)
    async def save(self, convo: Conversation) -> None:
        convo.pull_new_messages()  # 模拟落库消费 pending
        self.saved[convo.id.value] = convo
    async def load_full(self, cid: ConversationId) -> Conversation | None:
        return self.saved.get(cid.value)


class _FakeAgent:
    def __init__(self) -> None:
        self.last_request: AgentRequest | None = None
    async def run(self, request: AgentRequest) -> AgentResponse:
        self.last_request = request
        return AgentResponse(reply="这是助手回复")
    async def stream(self, request: AgentRequest):
        yield  # 未用到
        raise NotImplementedError


class _FakePublisher:
    def __init__(self) -> None:
        self.events: list = []
    async def publish(self, event) -> None:
        self.events.append(event)


def _use_case(repo, agent, publisher) -> SendMessageUseCase:
    return SendMessageUseCase(repo, agent, publisher, ContextWindowPolicy(size=20))


class SendMessageUseCaseTest(unittest.TestCase):
    def test_new_conversation_flow(self) -> None:
        repo, agent, pub = _FakeRepo(), _FakeAgent(), _FakePublisher()
        cmd = SendMessageCommand(content="查发票 12345", agent_id=AgentId(name="default_agent"))
        result = asyncio.run(_use_case(repo, agent, pub).execute(cmd))

        self.assertEqual(result.reply, "这是助手回复")
        # history 携带刚追加的用户消息
        self.assertEqual(agent.last_request.messages[-1], {"role": "user", "content": "查发票 12345"})
        # thread_id 用 conversation_id（链路追踪，不再驱动记忆）
        self.assertEqual(agent.last_request.thread_id, result.conversation_id)
        # 已保存
        self.assertIn(result.conversation_id, repo.saved)
        # 发出 ConversationStarted + AssistantResponded
        self.assertEqual(len(pub.events), 2)

    def test_continue_existing_conversation(self) -> None:
        repo, agent, pub = _FakeRepo(), _FakeAgent(), _FakePublisher()
        first = asyncio.run(_use_case(repo, agent, pub).execute(
            SendMessageCommand(content="第一句", agent_id=AgentId(name="default_agent"))
        ))
        pub.events.clear()
        second = asyncio.run(_use_case(repo, agent, pub).execute(
            SendMessageCommand(
                content="第二句", agent_id=AgentId(name="default_agent"),
                conversation_id=first.conversation_id,
            )
        ))
        self.assertEqual(second.conversation_id, first.conversation_id)
        # 续聊 history 含历史「第一句」与新「第二句」
        contents = [m["content"] for m in agent.last_request.messages]
        self.assertIn("第一句", contents)
        self.assertIn("第二句", contents)
        # 续聊只发 AssistantResponded（不再 Started）
        self.assertEqual(len(pub.events), 1)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_send_message_use_case -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'application.conversation.send_message'`

- [ ] **Step 3: 写最小实现**

创建 `src/application/conversation/send_message.py`：

```python
"""发送消息用例 —— 对话闭环编排。业务规则在 domain，此处只编排。"""
from __future__ import annotations

from application.conversation.commands import ChatResult, SendMessageCommand
from application.dto.agent_dto import AgentRequest
from application.ports.agent_service import AgentService
from application.ports.event_publisher import DomainEventPublisher
from domain.conversation.aggregate import Conversation
from domain.conversation.context_window import ContextWindowPolicy
from domain.conversation.repository import ConversationRepository
from domain.conversation.value_objects import ConversationId


class SendMessageUseCase:
    def __init__(
        self,
        repo: ConversationRepository,
        agent: AgentService,
        publisher: DomainEventPublisher,
        window: ContextWindowPolicy,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._publisher = publisher
        self._window = window

    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        convo = None
        if cmd.conversation_id:
            convo = await self._repo.get(
                ConversationId(value=cmd.conversation_id), window=self._window.size
            )
        if convo is None:
            convo = Conversation.start(cmd.agent_id)

        convo.post_user_message(cmd.content)                       # 领域
        history = self._window.select(convo.messages)              # 领域策略
        request = AgentRequest(
            messages=[{"role": m.role.value, "content": m.content} for m in history],
            thread_id=convo.id.value,   # 仅用于链路追踪，不再驱动记忆
        )
        response = await self._agent.run(request)                  # LangGraph 无状态
        convo.record_assistant_message(response.reply)            # 领域

        await self._repo.save(convo)
        for ev in convo.pull_events():
            await self._publisher.publish(ev)
        return ChatResult(conversation_id=convo.id.value, reply=response.reply)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_send_message_use_case -v`
Expected: PASS（2 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/application/conversation/send_message.py tests/test_send_message_use_case.py
git commit -m "feat: 新增 SendMessageUseCase 对话闭环用例"
```

---

## Task 8: SQLAlchemy 模型与仓储实现

两张表 + 显式映射（领域对象 ↔ ORM 行，不直接 `model_dump` 落库）。`seq` 由仓储在落库时分配（聚合不持 seq），`(conversation_id, seq)` 唯一。窗口加载只取最近 N；save 只 INSERT 新增消息，不重写历史。

**Files:**
- Modify: `pyproject.toml`（经 `uv add greenlet` + `uv add --dev aiosqlite`）
- Create: `src/infrastructure/conversation/__init__.py`
- Create: `src/infrastructure/conversation/models.py`
- Create: `src/infrastructure/conversation/repository.py`
- Test: `tests/test_conversation_repository.py`

**Interfaces:**
- Consumes: `Conversation`（Task 4）、Task 2 值对象、`ConversationRepository`（Task 6）、`AgentId`。
- Produces:
  - `Base`（DeclarativeBase）、`ConversationRow`、`ConversationMessageRow`、`async create_conversation_tables(engine) -> None`
  - `SqlAlchemyConversationRepository(session_factory: async_sessionmaker)` 实现 `ConversationRepository`。

- [ ] **Step 1: 新增依赖**

Run:
```bash
uv add greenlet
uv add --dev aiosqlite
```
Expected: `greenlet`（SQLAlchemy async 运行时必需）进 `dependencies`；`aiosqlite`（仅测试内存库）进 dev 依赖组；`uv.lock` 更新。

- [ ] **Step 2: 写失败测试**

创建 `tests/test_conversation_repository.py`（内存 SQLite + StaticPool）：

```python
"""SqlAlchemyConversationRepository 测试——append-only、窗口、全量、唯一约束。"""
from __future__ import annotations

import asyncio
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from domain.conversation.aggregate import Conversation
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId
from infrastructure.conversation.models import (
    ConversationMessageRow,
    create_conversation_tables,
)
from infrastructure.conversation.repository import SqlAlchemyConversationRepository


async def _make_repo() -> tuple[SqlAlchemyConversationRepository, async_sessionmaker]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    await create_conversation_tables(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return SqlAlchemyConversationRepository(factory), factory


def _agent() -> AgentId:
    return AgentId(name="default_agent", version="default")


class ConversationRepositoryTest(unittest.TestCase):
    def test_save_then_load_full_preserves_order(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("第一句")
            convo.record_assistant_message("第一答")
            await repo.save(convo)

            loaded = await repo.load_full(ConversationId(value=convo.id.value))
            self.assertEqual([m.content for m in loaded.messages], ["第一句", "第一答"])

        asyncio.run(run())

    def test_save_appends_without_rewriting_history(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("a")
            await repo.save(convo)  # seq 0

            # 续聊：重新加载后追加
            reloaded = await repo.load_full(ConversationId(value=convo.id.value))
            reloaded.post_user_message("b")
            reloaded.record_assistant_message("c")
            await repo.save(reloaded)  # seq 1,2

            full = await repo.load_full(ConversationId(value=convo.id.value))
            self.assertEqual([m.content for m in full.messages], ["a", "b", "c"])

        asyncio.run(run())

    def test_get_window_returns_recent_n(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            for i in range(5):
                convo.post_user_message(str(i))
            await repo.save(convo)

            windowed = await repo.get(ConversationId(value=convo.id.value), window=2)
            self.assertEqual([m.content for m in windowed.messages], ["3", "4"])

        asyncio.run(run())

    def test_get_missing_returns_none(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            self.assertIsNone(await repo.get(ConversationId(value="不存在")))

        asyncio.run(run())

    def test_unique_conversation_seq_constraint(self) -> None:
        async def run() -> None:
            from sqlalchemy.exc import IntegrityError

            repo, factory = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("x")
            await repo.save(convo)

            with self.assertRaises(IntegrityError):
                async with factory() as session:
                    session.add(ConversationMessageRow(
                        conversation_id=convo.id.value, seq=0, role="user",
                        content="重复 seq", tool_calls=[],
                        created_at=convo.created_at,
                    ))
                    await session.commit()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_repository -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'infrastructure.conversation'`

- [ ] **Step 4: 写最小实现**

创建 `src/infrastructure/conversation/__init__.py`：

```python
"""对话子域基础设施 —— SQLAlchemy 仓储实现、进程内事件发布器。"""
```

创建 `src/infrastructure/conversation/models.py`：

```python
"""对话持久化的 SQLAlchemy 2.0 ORM 模型与建表助手。"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ConversationRow(Base):
    __tablename__ = "conversation"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    agent_name: Mapped[str] = mapped_column(String(128))
    agent_version: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConversationMessageRow(Base):
    __tablename__ = "conversation_message"
    __table_args__ = (UniqueConstraint("conversation_id", "seq", name="uq_conversation_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(32), ForeignKey("conversation.id"))
    seq: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


async def create_conversation_tables(engine: AsyncEngine) -> None:
    """建对话相关表（MVP 用；生产改由 Alembic 迁移管理）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

创建 `src/infrastructure/conversation/repository.py`：

```python
"""对话仓储的 SQLAlchemy 实现 —— 显式映射，窗口加载 + 增量落库。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.conversation.aggregate import Conversation
from domain.conversation.repository import ConversationRepository
from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
    ToolCallRecord,
)
from domain.entities.agent_entity import AgentId
from infrastructure.conversation.models import ConversationMessageRow, ConversationRow


def _row_to_message(row: ConversationMessageRow) -> Message:
    return Message(
        role=MessageRole(row.role),
        content=row.content,
        created_at=row.created_at,
        tool_calls=tuple(ToolCallRecord(**tc) for tc in (row.tool_calls or [])),
    )


def _to_conversation(head: ConversationRow, messages: list[Message]) -> Conversation:
    return Conversation.reconstitute(
        id=ConversationId(value=head.id),
        agent_id=AgentId(name=head.agent_name, version=head.agent_version),
        status=ConversationStatus(head.status),
        created_at=head.created_at,
        updated_at=head.updated_at,
        messages=messages,
    )


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get(
        self, cid: ConversationId, *, window: int | None = None
    ) -> Conversation | None:
        async with self._session_factory() as session:
            head = await session.get(ConversationRow, cid.value)
            if head is None:
                return None
            stmt = (
                select(ConversationMessageRow)
                .where(ConversationMessageRow.conversation_id == cid.value)
                .order_by(ConversationMessageRow.seq.desc())
            )
            if window is not None:
                stmt = stmt.limit(window)
            rows = list((await session.execute(stmt)).scalars().all())
            rows.reverse()  # desc 取回后翻转为时间顺序
            return _to_conversation(head, [_row_to_message(r) for r in rows])

    async def load_full(self, cid: ConversationId) -> Conversation | None:
        return await self.get(cid, window=None)

    async def save(self, convo: Conversation) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                head = await session.get(ConversationRow, convo.id.value)
                if head is None:
                    session.add(
                        ConversationRow(
                            id=convo.id.value,
                            agent_name=convo.agent_id.name,
                            agent_version=convo.agent_id.version,
                            status=convo.status.value,
                            created_at=convo.created_at,
                            updated_at=convo.updated_at,
                        )
                    )
                else:
                    head.status = convo.status.value
                    head.updated_at = convo.updated_at

                new_messages = convo.pull_new_messages()
                if new_messages:
                    max_seq = (
                        await session.execute(
                            select(func.max(ConversationMessageRow.seq)).where(
                                ConversationMessageRow.conversation_id == convo.id.value
                            )
                        )
                    ).scalar()
                    next_seq = 0 if max_seq is None else max_seq + 1
                    for offset, m in enumerate(new_messages):
                        session.add(
                            ConversationMessageRow(
                                conversation_id=convo.id.value,
                                seq=next_seq + offset,
                                role=m.role.value,
                                content=m.content,
                                tool_calls=[tc.model_dump() for tc in m.tool_calls],
                                created_at=m.created_at,
                            )
                        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_repository -v`
Expected: PASS（5 个用例）

- [ ] **Step 6: 提交**

```bash
git add pyproject.toml uv.lock src/infrastructure/conversation/__init__.py src/infrastructure/conversation/models.py src/infrastructure/conversation/repository.py tests/test_conversation_repository.py
git commit -m "feat: 新增对话 SQLAlchemy 模型与仓储实现（append-only + 窗口加载）"
```

---

## Task 9: 进程内事件发布器

`DomainEventPublisher` 的最小进程内实现，按事件类型分发给订阅者。订阅者以后再挂（后续 spec）。

**Files:**
- Create: `src/infrastructure/conversation/event_publisher.py`
- Test: `tests/test_event_publisher.py`

**Interfaces:**
- Consumes: `DomainEvent`（Task 1）。
- Produces: `InMemoryEventPublisher()`；`subscribe(event_type: type, handler) -> None`；`async publish(event: DomainEvent) -> None`（handler 可同步或异步）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_event_publisher.py`：

```python
"""InMemoryEventPublisher 测试——按类型分发，未订阅类型 no-op。"""
from __future__ import annotations

import asyncio
import unittest

from domain.conversation.events import AssistantResponded, ConversationStarted
from infrastructure.conversation.event_publisher import InMemoryEventPublisher


class InMemoryEventPublisherTest(unittest.TestCase):
    def test_dispatch_to_subscriber(self) -> None:
        async def run() -> None:
            pub = InMemoryEventPublisher()
            seen: list = []
            pub.subscribe(ConversationStarted, lambda ev: seen.append(ev))
            await pub.publish(ConversationStarted(conversation_id="c1", agent_id="a"))
            self.assertEqual(len(seen), 1)

        asyncio.run(run())

    def test_async_handler_awaited(self) -> None:
        async def run() -> None:
            pub = InMemoryEventPublisher()
            seen: list = []

            async def handler(ev) -> None:
                seen.append(ev)

            pub.subscribe(ConversationStarted, handler)
            await pub.publish(ConversationStarted(conversation_id="c1", agent_id="a"))
            self.assertEqual(len(seen), 1)

        asyncio.run(run())

    def test_unsubscribed_type_is_noop(self) -> None:
        async def run() -> None:
            pub = InMemoryEventPublisher()
            await pub.publish(AssistantResponded(conversation_id="c1", content="x"))  # 不抛错

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_event_publisher -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'infrastructure.conversation.event_publisher'`

- [ ] **Step 3: 写最小实现**

创建 `src/infrastructure/conversation/event_publisher.py`：

```python
"""进程内领域事件发布器 —— 实现 DomainEventPublisher 端口（MVP）。"""
from __future__ import annotations

import inspect
import logging
from typing import Callable

from domain.shared.events import DomainEvent

logger = logging.getLogger("ai-finance")


class InMemoryEventPublisher:
    """按事件类型分发给订阅者；handler 可同步或异步。"""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = {}

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("领域事件订阅者回调异常: %s", type(event).__name__)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_event_publisher -v`
Expected: PASS（3 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/conversation/event_publisher.py tests/test_event_publisher.py
git commit -m "feat: 新增进程内领域事件发布器 InMemoryEventPublisher"
```

---

## Task 10: Agent 无状态化 + 对话用例装配工厂

把 ReAct Agent 切为无状态（`enable_memory=False`）；提供 `build_conversation_use_case(engine, agent_service)` 把仓储/发布器/窗口策略/用例装配起来。用内存 SQLite + 假 Agent 做一次真实闭环集成测试（穿过 domain+application+infrastructure）。

**Files:**
- Modify: `src/bootstrap/container.py`（Agent `enable_memory=False`；新增 `build_conversation_use_case`）
- Test: `tests/test_conversation_assembly.py`

**Interfaces:**
- Consumes: `SqlAlchemyConversationRepository`/`create_conversation_tables`（Task 8）、`InMemoryEventPublisher`（Task 9）、`SendMessageUseCase`（Task 7）、`ContextWindowPolicy`（Task 5）、`AgentService`。
- Produces: `build_conversation_use_case(engine: AsyncEngine, agent_service: AgentService, *, window_size: int = 20) -> SendMessageUseCase`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_assembly.py`：

```python
"""build_conversation_use_case 集成——真实仓储 + 假 Agent 跑完整闭环。"""
from __future__ import annotations

import asyncio
import unittest

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from application.conversation.commands import SendMessageCommand
from application.dto.agent_dto import AgentRequest, AgentResponse
from bootstrap.container import build_conversation_use_case
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId
from infrastructure.conversation.models import create_conversation_tables
from infrastructure.conversation.repository import SqlAlchemyConversationRepository


class _FakeAgent:
    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=f"收到 {len(request.messages)} 条消息")
    async def stream(self, request: AgentRequest):
        yield
        raise NotImplementedError


class ConversationAssemblyTest(unittest.TestCase):
    def test_two_round_conversation_persists(self) -> None:
        async def run() -> None:
            engine = create_async_engine(
                "sqlite+aiosqlite://", poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            await create_conversation_tables(engine)
            use_case = build_conversation_use_case(engine, _FakeAgent())

            first = await use_case.execute(
                SendMessageCommand(content="第一句", agent_id=AgentId(name="default_agent"))
            )
            second = await use_case.execute(
                SendMessageCommand(
                    content="第二句", agent_id=AgentId(name="default_agent"),
                    conversation_id=first.conversation_id,
                )
            )
            self.assertEqual(second.conversation_id, first.conversation_id)

            # 落库：两轮共 4 条消息（用户2 + 助手2）
            repo = SqlAlchemyConversationRepository(use_case._repo._session_factory)
            full = await repo.load_full(ConversationId(value=first.conversation_id))
            self.assertEqual(len(full.messages), 4)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_assembly -v`
Expected: FAIL —— `ImportError: cannot import name 'build_conversation_use_case'`

- [ ] **Step 3: 写最小实现**

在 `src/bootstrap/container.py`：

(a) 把创建 Agent 的调用改为无状态（找到 `create_react_agent(...)` 调用，增加 `enable_memory=False`）：

```python
    agent = create_react_agent(
        llm=llm,
        tools=lc_tools,
        system_prompt=prompt.system_text,
        enable_memory=False,   # 记忆迁入 Conversation 聚合，Agent 无状态
    )
```

> 若已实施路由计划（Agent 由 `build_agent_registry` 装配），则改动落在 `skill_agent_builder._build_one` 的 `create_react_agent(..., enable_memory=False)`。二者取其一，视集成顺序而定。

(b) 在文件末尾新增装配工厂（导入置于文件顶部相应位置）：

```python
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from application.conversation.send_message import SendMessageUseCase
from application.ports.agent_service import AgentService
from domain.conversation.context_window import ContextWindowPolicy
from infrastructure.conversation.event_publisher import InMemoryEventPublisher
from infrastructure.conversation.repository import SqlAlchemyConversationRepository


def build_conversation_use_case(
    engine: AsyncEngine,
    agent_service: AgentService,
    *,
    window_size: int = 20,
) -> SendMessageUseCase:
    """装配对话用例：SQLAlchemy 仓储 + 进程内发布器 + 窗口策略。"""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = SqlAlchemyConversationRepository(session_factory)
    publisher = InMemoryEventPublisher()
    window = ContextWindowPolicy(size=window_size)
    return SendMessageUseCase(repo, agent_service, publisher, window)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_assembly -v`
Expected: PASS（1 个用例）

- [ ] **Step 5: 回归 + 提交**

Run: `uv run python -m unittest discover -s tests`（确认 Agent 无状态改动不破坏既有测试）

```bash
git add src/bootstrap/container.py tests/test_conversation_assembly.py
git commit -m "feat: Agent 无状态化 + build_conversation_use_case 装配工厂"
```

---

## Task 11: FastAPI 对话路由 + DI

`POST /conversations/messages`：把请求翻译成命令、调用用例、翻译回响应。接口层只翻译，不碰 domain 内部或数据库。集成测试用 stub 用例覆盖 DI，不需真实库。

**Files:**
- Create: `src/interfaces/conversation/__init__.py`
- Create: `src/interfaces/conversation/schemas.py`
- Create: `src/interfaces/conversation/router.py`
- Modify: `src/bootstrap/dependencies.py`（`get_send_message_use_case`）
- Test: `tests/test_conversation_router.py`

**Interfaces:**
- Consumes: `SendMessageUseCase`（Task 7）、`SendMessageCommand/ChatResult`（Task 6）、`AgentId`。
- Produces:
  - `SendMessageBody(content: str, conversation_id: str | None=None, agent_name: str="default_agent", agent_version: str="default")`
  - `ChatResultResponse(conversation_id: str, reply: str)`
  - `interfaces.conversation.router.router`（`APIRouter(prefix="/conversations")`）
  - `get_send_message_use_case(request) -> SendMessageUseCase`（从 `app.state.send_message_use_case`，缺失 503）

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_router.py`：

```python
"""对话路由集成——注入 stub 用例，验证 /conversations/messages。"""
from __future__ import annotations

import asyncio
import unittest

import httpx

from application.conversation.commands import ChatResult, SendMessageCommand
from bootstrap.dependencies import get_send_message_use_case
from bootstrap.main import app


class _StubUseCase:
    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        return ChatResult(conversation_id="conv-1", reply=f"回复：{cmd.content}")


def _client() -> httpx.AsyncClient:
    app.dependency_overrides[get_send_message_use_case] = lambda: _StubUseCase()
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


class ConversationRouterTest(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_send_message(self) -> None:
        async def run() -> None:
            async with _client() as client:
                resp = await client.post("/conversations/messages", json={"content": "你好"})
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertEqual(body["conversation_id"], "conv-1")
                self.assertEqual(body["reply"], "回复：你好")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_router -v`
Expected: FAIL —— `ImportError: cannot import name 'get_send_message_use_case'`（或路由 404）

- [ ] **Step 3: 写最小实现**

创建 `src/interfaces/conversation/__init__.py`：

```python
"""对话子域接口层 —— FastAPI 路由与请求/响应 schema。"""
```

创建 `src/interfaces/conversation/schemas.py`：

```python
"""对话路由请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel


class SendMessageBody(BaseModel):
    content: str
    conversation_id: str | None = None
    agent_name: str = "default_agent"
    agent_version: str = "default"


class ChatResultResponse(BaseModel):
    conversation_id: str
    reply: str
```

在 `src/bootstrap/dependencies.py` 追加 DI（复用 Task 3 已引入的 `HTTPException`；若尚未引入需补导入）：

```python
from application.conversation.send_message import SendMessageUseCase


def get_send_message_use_case(request: Request) -> SendMessageUseCase:
    """注入 lifespan 装配的对话用例单例。"""
    use_case = getattr(request.app.state, "send_message_use_case", None)
    if use_case is None:
        raise HTTPException(status_code=503, detail="对话用例尚未就绪")
    return use_case
```

创建 `src/interfaces/conversation/router.py`：

```python
"""对话路由 —— POST /conversations/messages。接口层只翻译。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from application.conversation.commands import SendMessageCommand
from application.conversation.send_message import SendMessageUseCase
from bootstrap.dependencies import get_send_message_use_case
from domain.entities.agent_entity import AgentId
from interfaces.conversation.schemas import ChatResultResponse, SendMessageBody

router = APIRouter(prefix="/conversations", tags=["conversation"])


@router.post("/messages", response_model=ChatResultResponse)
async def send_message(
    body: SendMessageBody,
    use_case: SendMessageUseCase = Depends(get_send_message_use_case),
) -> ChatResultResponse:
    cmd = SendMessageCommand(
        content=body.content,
        agent_id=AgentId(name=body.agent_name, version=body.agent_version),
        conversation_id=body.conversation_id,
    )
    result = await use_case.execute(cmd)
    return ChatResultResponse(conversation_id=result.conversation_id, reply=result.reply)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_router -v`
Expected: PASS（1 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/conversation/__init__.py src/interfaces/conversation/schemas.py src/interfaces/conversation/router.py src/bootstrap/dependencies.py tests/test_conversation_router.py
git commit -m "feat: 新增 /conversations/messages 对话路由与 DI"
```

---

## Task 12: lifespan 装配 + 端到端手动验证

在 `lifespan` 建表、装配对话用例存 `app.state`、注册路由。用真实启动 + Postgres 验证完整闭环与持久化。

**Files:**
- Modify: `src/bootstrap/main.py`（建表 + 装配用例 + `include_router`）

**Interfaces:**
- Consumes: `build_conversation_use_case`（Task 10）、`create_conversation_tables`（Task 8）、对话 `router`（Task 11）、`app.state.agent_service`（若已实施 SSE/路由计划）或本地装配的 AgentService。

- [ ] **Step 1: lifespan 接线**

在 `src/bootstrap/main.py` 的 `lifespan` 中（`llm_repo.load()` 之后），装配对话用例。需要一个数据库引擎与一个 `AgentService`：

```python
from bootstrap.container import build_container, build_conversation_use_case
from infrastructure.config.database import create_db_engine
from infrastructure.conversation.models import create_conversation_tables
from interfaces.conversation.router import router as conversation_router

    # 数据库引擎 + 建对话表（MVP；生产用 Alembic）
    engine = create_db_engine()
    app.state.db_engine = engine
    await create_conversation_tables(engine)

    # AgentService：复用已预热单例（SSE/路由计划已设 app.state.agent_service）；
    # 若单独实施本计划，此处用 build_container 装配一个无状态 Agent。
    agent_service = getattr(app.state, "agent_service", None)
    if agent_service is None:
        container = await build_container(config=llm_repo.get(), skip_db=True)
        agent_service = container.agent_service
        app.state.agent_service = agent_service

    app.state.send_message_use_case = build_conversation_use_case(engine, agent_service)
    logger.info("对话用例已装配（Conversation 子域）")
```

在文件的路由注册处追加：

```python
app.include_router(conversation_router)
```

在 `lifespan` 的收尾（`await client.stop()` 附近）释放引擎：

```python
    await engine.dispose()
```

- [ ] **Step 2: 全量测试回归**

Run: `uv run python -m unittest discover -s tests`
Expected: OK（全绿；lifespan 改动不影响用 stub/override 的测试）

- [ ] **Step 3: 端到端手动验证**（需 `config/config.json` + Nacos + Postgres 可达；否则跳过并注明「端到端未验证」）

启动：`uv run python main.py` —— 日志出现 `对话用例已装配（Conversation 子域）`。

第一轮（新开对话）：
```bash
curl -s -X POST http://localhost:8000/conversations/messages \
  -H 'Content-Type: application/json' \
  -d '{"content":"我叫小王，帮我记住"}'
```
Expected: 返回 `{"conversation_id":"...","reply":"..."}`。

第二轮（带上一轮 conversation_id 续聊，验证记忆由领域提供）：
```bash
curl -s -X POST http://localhost:8000/conversations/messages \
  -H 'Content-Type: application/json' \
  -d '{"content":"我叫什么名字？","conversation_id":"<上一步返回的 id>"}'
```
Expected: 回复能引用「小王」——证明多轮记忆由 `Conversation` 聚合经 history 提供，而非 LangGraph `MemorySaver`。

- [ ] **Step 4: 校验持久化**

用 psql 或 DB 客户端确认 `conversation` 与 `conversation_message` 两表有对应记录、`(conversation_id, seq)` 递增。停止服务。

- [ ] **Step 5: 提交**

```bash
git add src/bootstrap/main.py
git commit -m "feat: lifespan 装配对话子域（建表 + 用例 + 路由），端到端多轮记忆由领域提供"
```

---

## Self-Review（写完计划后自查）

**1. Spec 覆盖**（对照设计 §3 In scope）：
- `Conversation` 聚合 + `Message` 等值对象 + 领域事件 + `ConversationRepository` 端口（domain）→ Task 2/3/4/6 ✅
- `SendMessageUseCase` 用例编排 + 命令/DTO（application）→ Task 6/7 ✅
- 仓储 SQLAlchemy 实现 + 最小进程内事件发布器（infrastructure）→ Task 8/9 ✅
- FastAPI 对话路由（interfaces）→ Task 11 ✅
- ReAct Agent 切无状态（`enable_memory=False`）→ Task 10 Step 3 ✅
- 上下文窗口策略（领域策略）→ Task 5 ✅
- 聚合体量处理：窗口加载 + 增量落库 + `load_full` → Task 8 仓储 + Task 4 `pull_new_messages`/`reconstitute` ✅
- 测试策略（领域纯单测、用例假件测、仓储 append/window/full/唯一约束）→ Task 4/7/8 ✅

**2. 占位符扫描**：无 TODO / 无「适当处理」；每个代码步骤给出完整代码。Task 10/12 对既有文件的改动以明确锚点（`create_react_agent` 调用、`lifespan`、路由注册处）描述，非占位。

**3. 类型一致性**：
- `Conversation.reconstitute(*, id, agent_id, status, created_at, updated_at, messages)`（Task 4）与仓储 `_to_conversation`（Task 8）调用一致。
- `pull_new_messages()`/`pull_events()`/`messages`（Task 4）贯穿用例（Task 7）与仓储（Task 8）一致。
- `ConversationRepository.get(cid, *, window)`/`save`/`load_full`（Task 6 端口）与实现（Task 8）、用例调用（Task 7）签名一致。
- `SendMessageCommand(content, agent_id, conversation_id)` / `ChatResult(conversation_id, reply)`（Task 6）贯穿用例（Task 7）与路由（Task 11）一致。
- `AgentRequest(messages=[{"role","content"}], thread_id)`（既有 DTO）与用例构造一致。
- `ContextWindowPolicy(size).select(...)`（Task 5）与用例、装配（Task 7/10）一致。

**4. 关键偏离设计的记录**（已在 Global Constraints 声明，评审可推翻）：
- 设计 §5.4/§8 的 `@dataclass` → 全改 Pydantic v2（CLAUDE.md 禁 dataclass）。
- 设计 §5.2 决策 D5「聚合根用普通类」→ 改 Pydantic + `PrivateAttr`（对齐既有 `AgentEntity` 先例 + 规则 11）。
- `seq` 由仓储在落库时分配（聚合不持 seq），使窗口加载/增量落库成立——设计只描述结果，未指定归属，此为落地细节。

**Out of scope 确认**（不做，见设计 §11 后续 spec）：账票模块对对话事件的订阅侧、工具↔业务接线、对话摘要/标题生成、按 token 预算的高级窗口、鉴权/多租户/owner 建模。**另注**：设计 §11.6 提到主干 `bootstrap` 引用不存在的 `NacosConfigClient` 遗留问题——经核对当前 `main.py`/`dependencies.py` 未见该引用（用的是 `infrastructure.client.nacos.NacosClient`），无需在本计划处理；若联调时确有残留错误引用，按独立修复项处理。
