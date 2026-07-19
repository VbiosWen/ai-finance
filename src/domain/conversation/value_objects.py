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
