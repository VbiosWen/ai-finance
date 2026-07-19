"""领域事件发布端口（application）。infrastructure 提供进程内实现。"""
from __future__ import annotations

from typing import Protocol

from domain.shared.events import DomainEvent


class DomainEventPublisher(Protocol):
    async def publish(self, event: DomainEvent) -> None:
        """发布一条领域事件给订阅者。"""
        ...
