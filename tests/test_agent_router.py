"""agent_router 集成测试——注入 stub AgentService，验证 /agent/chat[/stream]。"""
from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import AsyncIterator

import httpx

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from bootstrap.app import create_app
from interfaces.api.dependencies import get_agent_service
from tests.support import make_stub_container


class _ChatStub:
    """假 AgentService：stream 产出固定事件序列，run 返回固定响应。"""

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply="你好，我是账票助手", thread_id=request.thread_id, tool_calls_count=1)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="token", content="发")
        yield AgentStreamEvent(event_type="token", content="票")
        yield AgentStreamEvent(event_type="done", content="")


class AgentRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(make_stub_container())
        self.app.dependency_overrides[get_agent_service] = lambda: _ChatStub()

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_chat_non_stream(self) -> None:
        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/agent/chat", json={"messages": [{"role": "user", "content": "你好"}]})
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertEqual(body["reply"], "你好，我是账票助手")
                self.assertEqual(body["tool_calls_count"], 1)

        asyncio.run(run())

    def test_chat_stream_content_type_and_frames(self) -> None:
        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                async with client.stream(
                    "POST", "/agent/chat/stream",
                    json={"messages": [{"role": "user", "content": "你好"}]},
                ) as resp:
                    self.assertEqual(resp.status_code, 200)
                    self.assertTrue(resp.headers["content-type"].startswith("text/event-stream"))
                    events, datas = [], []
                    async for line in resp.aiter_lines():
                        if line.startswith("event:"):
                            events.append(line.split(":", 1)[1].strip())
                        elif line.startswith("data:"):
                            datas.append(json.loads(line.split(":", 1)[1].strip()))
                    self.assertEqual(events, ["token", "token", "done"])
                    self.assertEqual(datas[0]["content"], "发")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
