"""interfaces/http/schemas 测试——请求 DTO 转换与响应模型。"""
from __future__ import annotations

import unittest

from application.dto.agent_dto import AgentRequest
from interfaces.http.schemas import ChatMessage, ChatRequest, ChatResponse


class ChatRequestTest(unittest.TestCase):
    def test_to_agent_request_maps_messages(self) -> None:
        """messages 被转为 [{'role','content'}] 并构成 AgentRequest。"""
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="你好")],
            thread_id="t-1",
        )
        agent_req = req.to_agent_request()
        self.assertIsInstance(agent_req, AgentRequest)
        self.assertEqual(agent_req.thread_id, "t-1")
        self.assertEqual(agent_req.messages, [{"role": "user", "content": "你好"}])

    def test_default_role_is_user(self) -> None:
        """ChatMessage 未给 role 时默认 user。"""
        msg = ChatMessage(content="hi")
        self.assertEqual(msg.role, "user")

    def test_empty_request(self) -> None:
        """空请求转换为空 messages、thread_id 为 None。"""
        agent_req = ChatRequest().to_agent_request()
        self.assertEqual(agent_req.messages, [])
        self.assertIsNone(agent_req.thread_id)


class ChatResponseTest(unittest.TestCase):
    def test_fields(self) -> None:
        resp = ChatResponse(reply="答复", thread_id="t-1", tool_calls_count=2)
        self.assertEqual(resp.reply, "答复")
        self.assertEqual(resp.tool_calls_count, 2)


if __name__ == "__main__":
    unittest.main()
