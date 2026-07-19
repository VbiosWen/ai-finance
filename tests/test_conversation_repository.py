"""SqlAlchemyConversationRepository 测试——append-only、窗口、全量、唯一约束。"""
from __future__ import annotations

import asyncio
import unittest

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from domain.conversation.aggregate import Conversation
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId
from infrastructure.conversation.models import (
    ConversationMessageRow,
    create_conversation_tables,
)
from infrastructure.conversation.repository import SqlAlchemyConversationRepository


async def _make_repo() -> tuple[SqlAlchemyConversationRepository, async_sessionmaker]:
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    await create_conversation_tables(engine)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    return SqlAlchemyConversationRepository(factory), factory


def _agent() -> AgentId:
    return AgentId(name="default_agent", version="default")


class ConversationRepositoryTest(unittest.TestCase):
    def test_save_then_load_full_preserves_order(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("第一句")
            convo.record_assistant_message("第一答")
            await repo.save(convo)

            loaded = await repo.load_full(ConversationId(value=convo.id.value))
            self.assertEqual([m.content for m in loaded.messages], ["第一句", "第一答"])

        asyncio.run(run())

    def test_save_appends_without_rewriting_history(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("a")
            await repo.save(convo)  # seq 0

            # 续聊：重新加载后追加
            reloaded = await repo.load_full(ConversationId(value=convo.id.value))
            reloaded.post_user_message("b")
            reloaded.record_assistant_message("c")
            await repo.save(reloaded)  # seq 1,2

            full = await repo.load_full(ConversationId(value=convo.id.value))
            self.assertEqual([m.content for m in full.messages], ["a", "b", "c"])

        asyncio.run(run())

    def test_get_window_returns_recent_n(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            for i in range(5):
                convo.post_user_message(str(i))
            await repo.save(convo)

            windowed = await repo.get(ConversationId(value=convo.id.value), window=2)
            self.assertEqual([m.content for m in windowed.messages], ["3", "4"])

        asyncio.run(run())

    def test_get_missing_returns_none(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            self.assertIsNone(await repo.get(ConversationId(value="不存在")))

        asyncio.run(run())

    def test_unique_conversation_seq_constraint(self) -> None:
        async def run() -> None:
            from sqlalchemy.exc import IntegrityError

            repo, factory = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("x")
            await repo.save(convo)

            with self.assertRaises(IntegrityError):
                async with factory() as session:
                    session.add(ConversationMessageRow(
                        conversation_id=convo.id.value, seq=0, role="user",
                        content="重复 seq", tool_calls=[],
                        created_at=convo.created_at,
                    ))
                    await session.commit()

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
