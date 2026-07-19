"""对话子域值对象（不可变，零框架依赖）。"""
from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from domain.shared.id_generator import uuid7


class ConversationId(BaseModel):
    """对话标识（uuid7 hex，32 位小写十六进制，趋势递增）。"""

    value: str = Field(pattern=r"^[0-9a-f]{32}$")
    model_config = {"frozen": True}

    @classmethod
    def new(cls) -> "ConversationId":
        """生成新标识——单调 uuid7，ID 字典序即创建时间序。"""
        return cls(value=uuid7().hex)


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
