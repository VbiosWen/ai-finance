"""SendMessageUseCase 测试——闭环顺序、history 内容、事件发布、新开/续聊。"""
from __future__ import annotations

import asyncio
import unittest

from application.conversation.commands import SendMessageCommand
from application.conversation.send_message import SendMessageUseCase
from application.dto.agent_dto import AgentRequest, AgentResponse
from domain.conversation.aggregate import Conversation
from domain.conversation.context_window import ContextWindowPolicy
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId


class _FakeRepo:
    def __init__(self) -> None:
        self.saved: dict[str, Conversation] = {}
    async def get(self, cid: ConversationId, *, window=None) -> Conversation | None:
        return self.saved.get(cid.value)
    async def save(self, convo: Conversation) -> None:
        convo.pull_new_messages()  # 模拟落库消费 pending
        self.saved[convo.id.value] = convo
    async def load_full(self, cid: ConversationId) -> Conversation | None:
        return self.saved.get(cid.value)


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


def _use_case(repo, agent, publisher) -> SendMessageUseCase:
    return SendMessageUseCase(repo, agent, publisher, ContextWindowPolicy(size=20))


class SendMessageUseCaseTest(unittest.TestCase):
    def test_new_conversation_flow(self) -> None:
        repo, agent, pub = _FakeRepo(), _FakeAgent(), _FakePublisher()
        cmd = SendMessageCommand(content="查发票 12345", agent_id=AgentId(name="default_agent"))
        result = asyncio.run(_use_case(repo, agent, pub).execute(cmd))

        self.assertEqual(result.reply, "这是助手回复")
        # history 携带刚追加的用户消息
        self.assertEqual(agent.last_request.messages[-1], {"role": "user", "content": "查发票 12345"})
        # thread_id 用 conversation_id（链路追踪，不再驱动记忆）
        self.assertEqual(agent.last_request.thread_id, result.conversation_id)
        # 已保存
        self.assertIn(result.conversation_id, repo.saved)
        # 发出 ConversationStarted + AssistantResponded
        self.assertEqual(len(pub.events), 2)

    def test_continue_existing_conversation(self) -> None:
        repo, agent, pub = _FakeRepo(), _FakeAgent(), _FakePublisher()
        first = asyncio.run(_use_case(repo, agent, pub).execute(
            SendMessageCommand(content="第一句", agent_id=AgentId(name="default_agent"))
        ))
        pub.events.clear()
        second = asyncio.run(_use_case(repo, agent, pub).execute(
            SendMessageCommand(
                content="第二句", agent_id=AgentId(name="default_agent"),
                conversation_id=first.conversation_id,
            )
        ))
        self.assertEqual(second.conversation_id, first.conversation_id)
        # 续聊 history 含历史「第一句」与新「第二句」
        contents = [m["content"] for m in agent.last_request.messages]
        self.assertIn("第一句", contents)
        self.assertIn("第二句", contents)
        # 续聊只发 AssistantResponded（不再 Started）
        self.assertEqual(len(pub.events), 1)


if __name__ == "__main__":
    unittest.main()
