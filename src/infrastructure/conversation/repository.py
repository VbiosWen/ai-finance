"""对话仓储的 SQLAlchemy 实现 —— 显式映射，窗口加载 + 增量落库。"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from domain.conversation.aggregate import Conversation
from domain.conversation.repository import ConversationRepository
from domain.conversation.value_objects import (
    ConversationId,
    ConversationStatus,
    Message,
    MessageRole,
    ToolCallRecord,
)
from domain.entities.agent_entity import AgentId
from infrastructure.conversation.models import ConversationMessageRow, ConversationRow


def _row_to_message(row: ConversationMessageRow) -> Message:
    return Message(
        role=MessageRole(row.role),
        content=row.content,
        created_at=row.created_at,
        tool_calls=tuple(ToolCallRecord(**tc) for tc in (row.tool_calls or [])),
    )


def _to_conversation(head: ConversationRow, messages: list[Message]) -> Conversation:
    return Conversation.reconstitute(
        id=ConversationId(value=head.id),
        agent_id=AgentId(name=head.agent_name, version=head.agent_version),
        status=ConversationStatus(head.status),
        created_at=head.created_at,
        updated_at=head.updated_at,
        messages=messages,
    )


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory

    async def get(
        self, cid: ConversationId, *, window: int | None = None
    ) -> Conversation | None:
        async with self._session_factory() as session:
            head = await session.get(ConversationRow, cid.value)
            if head is None:
                return None
            stmt = (
                select(ConversationMessageRow)
                .where(ConversationMessageRow.conversation_id == cid.value)
                .order_by(ConversationMessageRow.seq.desc())
            )
            if window is not None:
                stmt = stmt.limit(window)
            rows = list((await session.execute(stmt)).scalars().all())
            rows.reverse()  # desc 取回后翻转为时间顺序
            return _to_conversation(head, [_row_to_message(r) for r in rows])

    async def get_head(self, cid: ConversationId) -> Conversation | None:
        async with self._session_factory() as session:
            head = await session.get(ConversationRow, cid.value)
            if head is None:
                return None
            return _to_conversation(head, [])

    async def load_full(self, cid: ConversationId) -> Conversation | None:
        return await self.get(cid, window=None)

    async def save(self, convo: Conversation) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                head = await session.get(ConversationRow, convo.id.value)
                if head is None:
                    session.add(
                        ConversationRow(
                            id=convo.id.value,
                            agent_name=convo.agent_id.name,
                            agent_version=convo.agent_id.version,
                            status=convo.status.value,
                            created_at=convo.created_at,
                            updated_at=convo.updated_at,
                        )
                    )
                else:
                    head.status = convo.status.value
                    head.updated_at = convo.updated_at

                new_messages = convo.pull_new_messages()
                if new_messages:
                    max_seq = (
                        await session.execute(
                            select(func.max(ConversationMessageRow.seq)).where(
                                ConversationMessageRow.conversation_id == convo.id.value
                            )
                        )
                    ).scalar()
                    next_seq = 0 if max_seq is None else max_seq + 1
                    for offset, m in enumerate(new_messages):
                        session.add(
                            ConversationMessageRow(
                                conversation_id=convo.id.value,
                                seq=next_seq + offset,
                                role=m.role.value,
                                content=m.content,
                                tool_calls=[tc.model_dump() for tc in m.tool_calls],
                                created_at=m.created_at,
                            )
                        )
