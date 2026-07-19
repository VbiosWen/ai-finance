"""领域事件基类 —— 聚合内产生的「已发生的事实」，跨模块解耦只经领域事件。"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


class DomainEvent(BaseModel):
    """所有领域事件的基类（不可变）。"""

    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}
