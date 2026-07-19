"""Conversation 聚合根测试——不变量、事件、pull 语义、重建。"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from domain.conversation.aggregate import Conversation, ConversationClosedError
from domain.conversation.events import (
    AssistantResponded,
    ConversationClosed,
    ConversationStarted,
)
from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
)
from domain.entities.agent_entity import AgentId


def _agent() -> AgentId:
    return AgentId(name="default_agent", version="default")


class ConversationAggregateTest(unittest.TestCase):
    def test_start_emits_started_event(self) -> None:
        convo = Conversation.start(_agent())
        self.assertEqual(convo.status, ConversationStatus.ACTIVE)
        events = convo.pull_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], ConversationStarted)
        self.assertEqual(convo.pull_events(), [])  # 取走后清空

    def test_post_and_record_append_in_order(self) -> None:
        convo = Conversation.start(_agent())
        convo.post_user_message("查发票 12345")
        convo.record_assistant_message("税额 13 元")
        roles = [m.role for m in convo.messages]
        self.assertEqual(roles, [MessageRole.USER, MessageRole.ASSISTANT])

    def test_record_emits_assistant_responded(self) -> None:
        convo = Conversation.start(_agent())
        convo.pull_events()  # 清掉 started
        convo.record_assistant_message("答复")
        events = convo.pull_events()
        self.assertEqual(len(events), 1)
        self.assertIsInstance(events[0], AssistantResponded)

    def test_closed_rejects_new_messages(self) -> None:
        convo = Conversation.start(_agent())
        convo.close()
        with self.assertRaises(ConversationClosedError):
            convo.post_user_message("还能说话吗")

    def test_close_emits_closed_event(self) -> None:
        convo = Conversation.start(_agent())
        convo.pull_events()
        convo.close()
        self.assertIsInstance(convo.pull_events()[0], ConversationClosed)

    def test_pull_new_messages_returns_and_clears(self) -> None:
        convo = Conversation.start(_agent())
        convo.post_user_message("a")
        convo.record_assistant_message("b")
        pending = convo.pull_new_messages()
        self.assertEqual(len(pending), 2)
        self.assertEqual(convo.pull_new_messages(), [])

    def test_reconstitute_no_events_no_pending(self) -> None:
        msgs = [Message(role=MessageRole.USER, content="旧消息", created_at=datetime.now(timezone.utc))]
        convo = Conversation.reconstitute(
            id=ConversationId(value="c1"), agent_id=_agent(),
            status=ConversationStatus.ACTIVE,
            created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc),
            messages=msgs,
        )
        self.assertEqual(len(convo.messages), 1)
        self.assertEqual(convo.pull_events(), [])       # 重建不发事件
        self.assertEqual(convo.pull_new_messages(), [])  # 重建不入 pending


if __name__ == "__main__":
    unittest.main()
