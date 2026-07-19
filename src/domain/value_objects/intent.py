"""意图识别与路由裁决的值对象（不可变，零框架依赖）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    """意图分类结果——分类器只出「技能 + 置信度」，不做裁决。"""

    target_skill: str | None = Field(default=None, description="最匹配技能名；None=识别不出/通用")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    reason: str = Field(default="", description="判断理由（可观测/日志）")

    model_config = {"frozen": True}


class RoutingDecision(BaseModel):
    """路由裁决结果——由 RoutingPolicy 产出。"""

    skill_name: str = Field(description="最终路由到的技能名")
    is_fallback: bool = Field(default=False, description="是否走了兜底")

    model_config = {"frozen": True}
