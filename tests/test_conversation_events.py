"""对话领域事件测试——字段与继承 occurred_at。"""
from __future__ import annotations

import unittest
from datetime import datetime

from domain.conversation.events import (
    AssistantResponded,
    ConversationClosed,
    ConversationStarted,
)
from domain.shared.events import DomainEvent


class ConversationEventsTest(unittest.TestCase):
    def test_started(self) -> None:
        ev = ConversationStarted(conversation_id="c1", agent_id="default_agent:default")
        self.assertIsInstance(ev, DomainEvent)
        self.assertEqual(ev.conversation_id, "c1")
        self.assertIsInstance(ev.occurred_at, datetime)

    def test_assistant_responded_default_tool_calls(self) -> None:
        ev = AssistantResponded(conversation_id="c1", content="答复")
        self.assertEqual(ev.tool_calls, ())

    def test_closed(self) -> None:
        self.assertEqual(ConversationClosed(conversation_id="c1").conversation_id, "c1")


if __name__ == "__main__":
    unittest.main()
