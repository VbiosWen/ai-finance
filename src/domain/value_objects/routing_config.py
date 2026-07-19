"""路由策略参数（不可变值对象）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RoutingConfig(BaseModel):
    """置信度阈值 + 兜底技能名等策略参数。"""

    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    fallback_skill_name: str = Field(default="general")

    model_config = {"frozen": True}
