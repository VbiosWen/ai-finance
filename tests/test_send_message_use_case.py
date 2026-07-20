"""SendMessageUseCase 测试——只喂最新一条、thread_id 驱动记忆、事件、领域把门。"""
from __future__ import annotations

import asyncio
import unittest

from application.conversation.commands import SendMessageCommand
from application.conversation.send_message import SendMessageUseCase
from application.dto.agent_dto import AgentRequest, AgentResponse
from domain.conversation.aggregate import Conversation, ConversationClosedError
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId


class _FakeRepo:
    def __init__(self) -> None:
        self.saved: dict[str, Conversation] = {}

    async def get_head(self, cid: ConversationId) -> Conversation | None:
        return self.saved.get(cid.value)

    async def save(self, convo: Conversation) -> None:
        convo.pull_new_messages()  # 模拟落库消费 pending
        self.saved[convo.id.value] = convo


class _FakeAgent:
    def __init__(self) -> None:
        self.last_request: AgentRequest | None = None

    async def run(self, request: AgentRequest) -> AgentResponse:
        self.last_request = request
        return AgentResponse(reply="这是助手回复")

    async def stream(self, request: AgentRequest):
        yield  # 未用到
        raise NotImplementedError


class _FakePublisher:
    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


class SendMessageUseCaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo, self.agent, self.pub = _FakeRepo(), _FakeAgent(), _FakePublisher()
        self.use_case = SendMessageUseCase(self.repo, self.agent, self.pub)

    def test_new_conversation_feeds_latest_only(self) -> None:
        result = asyncio.run(self.use_case.execute(
            SendMessageCommand(content="查发票 12345", agent_id=AgentId(name="default_agent"))
        ))
        self.assertEqual(result.reply, "这是助手回复")
        # 只喂最新一条(记忆由 checkpointer 按 thread_id 回放)
        self.assertEqual(
            self.agent.last_request.messages,
            [{"role": "user", "content": "查发票 12345"}],
        )
        # thread_id = conversation_id,驱动记忆
        self.assertEqual(self.agent.last_request.thread_id, result.conversation_id)
        self.assertIn(result.conversation_id, self.repo.saved)
        self.assertEqual(len(self.pub.events), 2)  # Started + AssistantResponded

    def test_continue_feeds_latest_only(self) -> None:
        first = asyncio.run(self.use_case.execute(
            SendMessageCommand(content="第一句", agent_id=AgentId(name="default_agent"))
        ))
        self.pub.events.clear()
        second = asyncio.run(self.use_case.execute(
            SendMessageCommand(
                content="第二句", agent_id=AgentId(name="default_agent"),
                conversation_id=first.conversation_id,
            )
        ))
        self.assertEqual(second.conversation_id, first.conversation_id)
        # 续聊同样只带最新一条,不再回放「第一句」
        self.assertEqual(
            self.agent.last_request.messages,
            [{"role": "user", "content": "第二句"}],
        )
        self.assertEqual(len(self.pub.events), 1)  # 仅 AssistantResponded

    def test_closed_conversation_rejected_before_agent(self) -> None:
        convo = Conversation.start(AgentId(name="default_agent"))
        convo.close()
        self.repo.saved[convo.id.value] = convo
        with self.assertRaises(ConversationClosedError):
            asyncio.run(self.use_case.execute(SendMessageCommand(
                content="还在吗", agent_id=AgentId(name="default_agent"),
                conversation_id=convo.id.value,
            )))
        self.assertIsNone(self.agent.last_request)  # 领域把门在进图之前


if __name__ == "__main__":
    unittest.main()
