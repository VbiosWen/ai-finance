"""上下文窗口策略 —— 领域决策，可插拔。MVP 用「最近 N 条」。"""
from __future__ import annotations

from domain.conversation.value_objects import Message


class ContextWindowPolicy:
    """裁剪喂给 Agent 的上下文窗口。"""

    def __init__(self, size: int = 20) -> None:
        self.size = size

    def select(self, messages: tuple[Message, ...]) -> list[Message]:
        """默认返回最近 size 条；size<=0 时返回全部。"""
        if self.size <= 0:
            return list(messages)
        return list(messages[-self.size :])
