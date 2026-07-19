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
