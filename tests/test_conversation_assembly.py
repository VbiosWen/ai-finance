"""build_conversation_use_case 集成——真实仓储 + 假 Agent 跑完整闭环。"""
from __future__ import annotations

import asyncio
import unittest

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import StaticPool

from application.conversation.commands import SendMessageCommand
from application.dto.agent_dto import AgentRequest, AgentResponse
from bootstrap.container import build_conversation_use_case
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId
from infrastructure.conversation.models import create_conversation_tables
from infrastructure.conversation.repository import SqlAlchemyConversationRepository


class _FakeAgent:
    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=f"收到 {len(request.messages)} 条消息")
    async def stream(self, request: AgentRequest):
        yield
        raise NotImplementedError


class ConversationAssemblyTest(unittest.TestCase):
    def test_two_round_conversation_persists(self) -> None:
        async def run() -> None:
            engine = create_async_engine(
                "sqlite+aiosqlite://", poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            await create_conversation_tables(engine)
            use_case = build_conversation_use_case(engine, _FakeAgent())

            first = await use_case.execute(
                SendMessageCommand(content="第一句", agent_id=AgentId(name="default_agent"))
            )
            second = await use_case.execute(
                SendMessageCommand(
                    content="第二句", agent_id=AgentId(name="default_agent"),
                    conversation_id=first.conversation_id,
                )
            )
            self.assertEqual(second.conversation_id, first.conversation_id)

            # 落库：两轮共 4 条消息（用户2 + 助手2）
            repo = SqlAlchemyConversationRepository(use_case._repo._session_factory)
            full = await repo.load_full(ConversationId(value=first.conversation_id))
            self.assertEqual(len(full.messages), 4)

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
