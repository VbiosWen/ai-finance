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
