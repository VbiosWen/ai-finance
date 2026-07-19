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
