"""进程内领域事件发布器 —— 实现 DomainEventPublisher 端口（MVP）。"""
from __future__ import annotations

import inspect
import logging
from typing import Callable

from domain.shared.events import DomainEvent

logger = logging.getLogger("ai-finance")


class InMemoryEventPublisher:
    """按事件类型分发给订阅者；handler 可同步或异步。"""

    def __init__(self) -> None:
        self._handlers: dict[type, list[Callable]] = {}

    def subscribe(self, event_type: type, handler: Callable) -> None:
        self._handlers.setdefault(event_type, []).append(handler)

    async def publish(self, event: DomainEvent) -> None:
        for handler in self._handlers.get(type(event), []):
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception("领域事件订阅者回调异常: %s", type(event).__name__)
