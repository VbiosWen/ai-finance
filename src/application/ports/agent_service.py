"""AI Agent 服务端口——定义 Agent 调用的抽象契约。

应用层依赖此端口，基础设施层提供 LangChain 实现。
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Protocol, runtime_checkable

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent


@runtime_checkable
class AgentService(Protocol):
    """Agent 服务抽象端口。

    定义 Agent 的标准调用方式：
    - run: 同步/非流式调用，返回完整结果。
    - stream: 异步流式调用，逐事件推送（SSE）。

    基础设施层使用 LangChain 的 create_agent 实现此端口。
    """

    async def run(self, request: AgentRequest) -> AgentResponse:
        """非流式调用 Agent，返回完整结果。

        Args:
            request: 包含消息列表和可选 thread_id 的请求。

        Returns:
            AgentResponse: 包含最终回复文本的响应。
        """
        ...

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        """流式调用 Agent，逐事件推送。

        Args:
            request: 包含消息列表和可选 thread_id 的请求。

        Yields:
            AgentStreamEvent: 事件流（token / tool_start / tool_end / done / error）。
        """
        ...
