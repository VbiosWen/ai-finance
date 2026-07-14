"""LangChain Agent 适配器——实现 AgentService 端口。

将基础设施层装配的 LangChain ReAct Agent，包装为 application 层
定义的 AgentService 端口，供上层（FastAPI 路由等）使用。

职责：
- 消息格式转换（dict ↔ LangChain Message）
- 非流式调用（run）→ ainvoke
- 流式调用（stream）→ astream_events，逐事件推送
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.ports.agent_service import AgentService

logger = logging.getLogger("ai-finance")


class LangChainAgentService:
    """基于 LangChain 的 AgentService 实现。

    封装 LangGraph 编译后的 agent，实现 run 与 stream 两种调用模式。
    由 bootstrap/container.py 在启动时装配。

    Usage:
        agent = create_react_agent(llm, tools, system_prompt)
        service = LangChainAgentService(agent)
        response = await service.run(AgentRequest(messages=[...]))
    """

    def __init__(self, agent: Any) -> None:
        self._agent = agent

    # ------------------------------------------------------------------
    # AgentService 端口实现
    # ------------------------------------------------------------------

    async def run(self, request: AgentRequest) -> AgentResponse:
        """非流式调用 Agent，返回完整结果。"""
        messages = _to_langchain_messages(request.messages)
        config = _build_config(request.thread_id)

        logger.debug(
            "Agent run: thread_id=%s, messages=%d",
            request.thread_id,
            len(messages),
        )

        result = await self._agent.ainvoke({"messages": messages}, config=config)

        result_messages: list[Any] = result.get("messages", [])
        reply = _extract_last_ai_content(result_messages)
        tool_call_count = _count_tool_calls(result_messages)

        return AgentResponse(
            reply=reply,
            thread_id=request.thread_id,
            tool_calls_count=tool_call_count,
        )

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        """流式调用 Agent，逐事件推送（适用 SSE）。"""
        messages = _to_langchain_messages(request.messages)
        config = _build_config(request.thread_id)

        logger.debug(
            "Agent stream: thread_id=%s, messages=%d",
            request.thread_id,
            len(messages),
        )

        try:
            async for event in self._agent.astream_events(
                {"messages": messages},
                config=config,
                version="v2",
            ):
                mapped = _map_event(event)
                if mapped is not None:
                    yield mapped
        except Exception as exc:
            logger.error("Agent stream 异常: %s", exc)
            yield AgentStreamEvent(
                event_type="error",
                content=str(exc),
            )


# ---------------------------------------------------------------------------
# 模块级工具函数
# ---------------------------------------------------------------------------


def _to_langchain_messages(
    messages: list[dict[str, str]],
) -> list[HumanMessage | AIMessage | SystemMessage]:
    """将 Agent DTO 消息列表转为 LangChain Message 对象列表。"""
    role_to_cls: dict[str, type] = {
        "user": HumanMessage,
        "assistant": AIMessage,
        "system": SystemMessage,
    }
    result: list[HumanMessage | AIMessage | SystemMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        cls = role_to_cls.get(role, HumanMessage)
        result.append(cls(content=content))
    return result


def _build_config(thread_id: str | None) -> dict[str, Any]:
    """构建 LangGraph 运行配置。"""
    if thread_id:
        return {"configurable": {"thread_id": thread_id}}
    return {}


def _extract_last_ai_content(messages: list[Any]) -> str:
    """从消息列表中提取最后一条 AI 消息的内容。"""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            return _safe_content(msg)
    return ""


def _count_tool_calls(messages: list[Any]) -> int:
    """统计消息列表中的工具调用次数。"""
    count = 0
    for msg in messages:
        if isinstance(msg, AIMessage) and hasattr(msg, "tool_calls"):
            count += len(msg.tool_calls or [])
    return count


def _safe_content(msg: Any) -> str:
    """安全提取消息内容。"""
    content = msg.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
        return "".join(parts)
    return str(content)


def _map_event(event: dict[str, Any]) -> AgentStreamEvent | None:
    """将 LangChain astream_events 事件映射为 AgentStreamEvent。"""
    event_name: str = event.get("event", "")
    now = datetime.now(timezone.utc)

    # --- token 事件 ---
    if event_name == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        if chunk and hasattr(chunk, "content") and isinstance(chunk.content, str):
            return AgentStreamEvent(
                event_type="token",
                content=chunk.content,
                timestamp=now,
            )
        return None

    # --- 工具开始 ---
    if event_name == "on_tool_start":
        tool_name = event.get("name", "unknown")
        tool_input = event.get("data", {}).get("input", "")
        return AgentStreamEvent(
            event_type="tool_start",
            tool_name=tool_name,
            content=str(tool_input),
            timestamp=now,
        )

    # --- 工具结束 ---
    if event_name == "on_tool_end":
        tool_name = event.get("name", "unknown")
        output = event.get("data", {}).get("output", "")
        return AgentStreamEvent(
            event_type="tool_end",
            tool_name=tool_name,
            content=str(output),
            timestamp=now,
        )

    # --- 顶层 chain 结束 → 对话完成 ---
    if event_name == "on_chain_end":
        if event.get("name") == "LangGraph":
            return AgentStreamEvent(
                event_type="done",
                content="",
                timestamp=now,
            )

    return None
