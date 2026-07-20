"""对话仓储端口（domain）。聊天闭环用窗口加载 + 增量落库；审计走全量。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from domain.conversation.aggregate import Conversation
from domain.conversation.value_objects import ConversationId


class ConversationRepository(ABC):
    @abstractmethod
    async def get(
        self, cid: ConversationId, *, window: int | None = None
    ) -> Conversation | None:
        """加载对话头 + 最近 window 条消息（None 表示全量）。"""
        ...

    @abstractmethod
    async def get_head(self, cid: ConversationId) -> Conversation | None:
        """只加载对话头(存在性/状态把门用),不载任何历史消息。"""
        ...

    @abstractmethod
    async def save(self, convo: Conversation) -> None:
        """upsert 对话头 + 只 INSERT pull_new_messages() 的新消息，不重写历史。"""
        ...

    @abstractmethod
    async def load_full(self, cid: ConversationId) -> Conversation | None:
        """审计/查询用：全量加载。"""
        ...
