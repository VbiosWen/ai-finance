"""interfaces/http/sse 测试——AgentStreamEvent 流 → SSE 帧字典。"""
from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentStreamEvent
from interfaces.http.sse import to_sse_events


async def _make_stream(events: list[AgentStreamEvent]) -> AsyncIterator[AgentStreamEvent]:
    for ev in events:
        yield ev


async def _collect(events: list[AgentStreamEvent]) -> list[dict]:
    return [frame async for frame in to_sse_events(_make_stream(events))]


class ToSseEventsTest(unittest.TestCase):
    def test_frame_shape(self) -> None:
        """每个事件产出 {'event','data'}，event 取事件类型，data 为合法 JSON。"""
        events = [
            AgentStreamEvent(event_type="token", content="发票"),
            AgentStreamEvent(event_type="done", content=""),
        ]
        frames = asyncio.run(_collect(events))
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["event"], "token")
        parsed = json.loads(frames[0]["data"])
        self.assertEqual(parsed["event_type"], "token")
        self.assertEqual(parsed["content"], "发票")
        self.assertEqual(frames[1]["event"], "done")

    def test_empty_stream(self) -> None:
        """空事件流产出空帧列表。"""
        self.assertEqual(asyncio.run(_collect([])), [])


if __name__ == "__main__":
    unittest.main()
