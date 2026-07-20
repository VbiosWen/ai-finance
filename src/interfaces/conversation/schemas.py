"""对话路由请求/响应模型。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SendMessageBody(BaseModel):
    content: str
    # None = 新开对话；传值必须是 32 位小写 hex（与 ConversationId 同款约束），非法格式边界 422
    conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    agent_name: str = "default_agent"
    agent_version: str = "default"


class ChatResultResponse(BaseModel):
    conversation_id: str
    reply: str
