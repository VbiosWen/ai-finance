"""SSE 编码器 —— 把领域事件流编码为 sse-starlette 帧字典。

整个 AgentStreamEvent 序列化为 JSON 放入 data，换行天然转义，
规避 SSE「多行 data」陷阱；event 取事件类型，供前端按类型分派。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentStreamEvent


async def to_sse_events(
    events: AsyncIterator[AgentStreamEvent],
) -> AsyncIterator[dict]:
    """把 AgentStreamEvent 流编码为 sse-starlette 可消费的帧字典。"""
    async for ev in events:
        yield {"event": ev.event_type, "data": ev.model_dump_json()}
