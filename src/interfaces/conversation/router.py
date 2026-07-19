"""对话路由 —— POST /conversations/messages。接口层只翻译。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from application.conversation.commands import SendMessageCommand
from application.conversation.send_message import SendMessageUseCase
from domain.entities.agent_entity import AgentId
from interfaces.api.dependencies import get_send_message_use_case
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
