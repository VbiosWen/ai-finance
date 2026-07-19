"""命令/结果 DTO 与仓储端口测试。"""
from __future__ import annotations

import unittest

from application.conversation.commands import ChatResult, SendMessageCommand
from domain.conversation.repository import ConversationRepository
from domain.entities.agent_entity import AgentId


class CommandsTest(unittest.TestCase):
    def test_send_message_command(self) -> None:
        cmd = SendMessageCommand(content="你好", agent_id=AgentId(name="default_agent"))
        self.assertEqual(cmd.content, "你好")
        self.assertIsNone(cmd.conversation_id)

    def test_chat_result(self) -> None:
        self.assertEqual(ChatResult(conversation_id="c1", reply="答复").reply, "答复")

    def test_repository_is_abstract(self) -> None:
        with self.assertRaises(TypeError):
            ConversationRepository()  # type: ignore[abstract]


if __name__ == "__main__":
    unittest.main()
