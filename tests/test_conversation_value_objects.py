"""对话值对象测试——枚举、frozen Message、ToolCallRecord。"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
    ToolCallRecord,
)


class ValueObjectsTest(unittest.TestCase):
    def test_conversation_id_new_is_valid_and_increasing(self) -> None:
        a, b = ConversationId.new(), ConversationId.new()
        self.assertRegex(a.value, r"^[0-9a-f]{32}$")
        self.assertLess(a.value, b.value)  # hex 字典序 = 生成序

    def test_conversation_id_rejects_invalid(self) -> None:
        for bad in ("abc", "A" * 32, "g" * 32, "0" * 31, "0" * 33):
            with self.assertRaises(ValidationError):
                ConversationId(value=bad)

    def test_conversation_id_accepts_legacy_hex(self) -> None:
        # 存量 uuid4 hex 同为 32 位小写十六进制，必须继续可用
        self.assertEqual(ConversationId(value="0" * 32).value, "0" * 32)

    def test_roles(self) -> None:
        self.assertEqual(MessageRole.USER.value, "user")
        self.assertEqual(ConversationStatus.CLOSED.value, "closed")

    def test_message_frozen(self) -> None:
        msg = Message(role=MessageRole.USER, content="你好", created_at=datetime.now(timezone.utc))
        self.assertEqual(msg.tool_calls, ())
        with self.assertRaises(ValidationError):
            msg.content = "改不了"  # type: ignore[misc]

    def test_message_with_tool_calls(self) -> None:
        tc = ToolCallRecord(tool_name="lookup_invoice", args_summary="INV-001")
        msg = Message(
            role=MessageRole.ASSISTANT, content="查到了",
            created_at=datetime.now(timezone.utc), tool_calls=(tc,),
        )
        self.assertEqual(msg.tool_calls[0].tool_name, "lookup_invoice")


if __name__ == "__main__":
    unittest.main()
