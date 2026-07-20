"""对话路由集成——注入 stub 用例，验证 /conversations/messages。"""
from __future__ import annotations

import asyncio
import unittest

import httpx

from application.conversation.commands import ChatResult, SendMessageCommand
from bootstrap.app import create_app
from interfaces.api.dependencies import get_send_message_use_case
from tests.support import make_stub_container


class _StubUseCase:
    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        return ChatResult(conversation_id="conv-1", reply=f"回复：{cmd.content}")


class ConversationRouterTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(make_stub_container())
        self.app.dependency_overrides[get_send_message_use_case] = lambda: _StubUseCase()

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_send_message(self) -> None:
        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post("/conversations/messages", json={"content": "你好"})
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertEqual(body["conversation_id"], "conv-1")
                self.assertEqual(body["reply"], "回复：你好")

        asyncio.run(run())

    def test_malformed_conversation_id_rejected_422(self) -> None:
        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/conversations/messages",
                    json={"content": "你好", "conversation_id": "not-a-valid-id"},
                )
                self.assertEqual(resp.status_code, 422)  # 边界拒绝，不进用例

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
