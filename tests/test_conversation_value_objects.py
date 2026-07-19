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
    def test_conversation_id(self) -> None:
        self.assertEqual(ConversationId(value="abc").value, "abc")

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
