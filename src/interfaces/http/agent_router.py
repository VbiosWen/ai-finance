"""Agent 对话路由 —— 流式（SSE）与非流式两端点。

接口层只翻译：ChatRequest → AgentRequest → 调 AgentService → 翻译回响应。
不含业务逻辑，路由细节对 AgentService 端口透明。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from application.ports.agent_service import AgentService
from interfaces.api.dependencies import get_agent_service
from interfaces.http.schemas import ChatRequest, ChatResponse
from interfaces.http.sse import to_sse_events

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
) -> EventSourceResponse:
    """SSE 流式对话：逐 AgentStreamEvent 推送，ping=15s 保活。"""
    stream = agent.stream(req.to_agent_request())
    return EventSourceResponse(to_sse_events(stream), ping=15)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
) -> ChatResponse:
    """非流式对话：返回完整回复。"""
    resp = await agent.run(req.to_agent_request())
    return ChatResponse(
        reply=resp.reply,
        thread_id=resp.thread_id,
        tool_calls_count=resp.tool_calls_count,
        routed_skill=resp.routed_skill,
    )
