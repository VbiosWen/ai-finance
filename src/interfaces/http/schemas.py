"""HTTP 请求/响应模型 —— interfaces 层只做翻译，不含业务逻辑。

把 HTTP JSON 翻译为 application 层 AgentRequest，把 AgentResponse 翻译回 HTTP。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from application.dto.agent_dto import AgentRequest


class ChatMessage(BaseModel):
    """单条对话消息。"""

    role: Literal["user", "assistant", "system"] = "user"
    content: str


class ChatRequest(BaseModel):
    """对话请求体（流式/非流式共用）。"""

    messages: list[ChatMessage] = Field(default_factory=list)
    thread_id: str | None = None

    def to_agent_request(self) -> AgentRequest:
        """翻译为 application 层 AgentRequest。"""
        return AgentRequest(
            messages=[m.model_dump() for m in self.messages],
            thread_id=self.thread_id,
        )


class ChatResponse(BaseModel):
    """非流式对话响应体。"""

    reply: str
    thread_id: str | None = None
    tool_calls_count: int = 0
