"""对话用例的命令与结果 DTO（Pydantic v2）。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from domain.entities.agent_entity import AgentId


class SendMessageCommand(BaseModel):
    content: str
    agent_id: AgentId
    conversation_id: str | None = None  # 空 = 新开对话

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ChatResult(BaseModel):
    conversation_id: str
    reply: str
