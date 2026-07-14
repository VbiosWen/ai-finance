"""Agent DTO 测试——验证 Pydantic 模型的序列化与校验。"""
from __future__ import annotations

import json
import unittest

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent


class AgentRequestTest(unittest.TestCase):
    """AgentRequest DTO 测试。"""

    def test_default_values(self) -> None:
        """未提供参数时使用默认值。"""
        req = AgentRequest()
        self.assertEqual(req.messages, [])
        self.assertIsNone(req.thread_id)

    def test_with_messages(self) -> None:
        """正常带消息的请求。"""
        req = AgentRequest(
            messages=[{"role": "user", "content": "查询发票"}],
            thread_id="thread-123",
        )
        self.assertEqual(len(req.messages), 1)
        self.assertEqual(req.thread_id, "thread-123")
        self.assertEqual(req.messages[0]["content"], "查询发票")

    def test_serialization_roundtrip(self) -> None:
        """序列化后反序列化保持数据一致。"""
        req = AgentRequest(
            messages=[{"role": "user", "content": "测试"}],
            thread_id="t1",
        )
        data = req.model_dump()
        restored = AgentRequest(**data)
        self.assertEqual(restored.thread_id, "t1")
        self.assertEqual(restored.messages, [{"role": "user", "content": "测试"}])

    def test_json_deserialization(self) -> None:
        """从 JSON 字符串反序列化。"""
        json_str = json.dumps({
            "messages": [{"role": "user", "content": "hello"}],
            "thread_id": "42",
        })
        req = AgentRequest.model_validate_json(json_str)
        self.assertEqual(req.thread_id, "42")


class AgentResponseTest(unittest.TestCase):
    """AgentResponse DTO 测试。"""

    def test_basic_response(self) -> None:
        """基本响应字段正确。"""
        resp = AgentResponse(reply="发票 INV-001 金额 100.00 元")
        self.assertEqual(resp.reply, "发票 INV-001 金额 100.00 元")
        self.assertEqual(resp.tool_calls_count, 0)
        self.assertIsNone(resp.thread_id)

    def test_with_tool_calls(self) -> None:
        """带工具调用次数的响应。"""
        resp = AgentResponse(
            reply="查询完成",
            thread_id="t-1",
            tool_calls_count=3,
        )
        self.assertEqual(resp.tool_calls_count, 3)
        self.assertEqual(resp.thread_id, "t-1")


class AgentStreamEventTest(unittest.TestCase):
    """AgentStreamEvent DTO 测试。"""

    def test_token_event(self) -> None:
        """token 类型事件。"""
        evt = AgentStreamEvent(event_type="token", content="你好")
        self.assertEqual(evt.event_type, "token")
        self.assertEqual(evt.content, "你好")
        self.assertIsNotNone(evt.timestamp)

    def test_tool_start_event(self) -> None:
        """工具开始事件。"""
        evt = AgentStreamEvent(
            event_type="tool_start",
            tool_name="lookup_invoice",
            content='{"invoice_id": "INV-001"}',
        )
        self.assertEqual(evt.tool_name, "lookup_invoice")

    def test_error_event(self) -> None:
        """错误事件。"""
        evt = AgentStreamEvent(event_type="error", content="超时")
        self.assertEqual(evt.event_type, "error")


if __name__ == "__main__":
    unittest.main()
