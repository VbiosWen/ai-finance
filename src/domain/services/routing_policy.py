"""路由裁决领域服务 —— 无状态，脱离 LLM 可单测。"""
from __future__ import annotations

from domain.value_objects.intent import IntentClassification, RoutingDecision
from domain.value_objects.routing_config import RoutingConfig


class RoutingPolicy:
    """把「识别结果」裁决为「路由目标」。"""

    def __init__(self, config: RoutingConfig) -> None:
        self._config = config

    @property
    def fallback_name(self) -> str:
        return self._config.fallback_skill_name

    def decide(self, c: IntentClassification, available: set[str]) -> RoutingDecision:
        """置信度阈值裁决：低置信/无匹配/不在可路由集 → 兜底。"""
        target = c.target_skill
        if (
            target is None
            or target not in available
            or c.confidence < self._config.confidence_threshold
        ):
            return RoutingDecision(skill_name=self._config.fallback_skill_name, is_fallback=True)
        return RoutingDecision(skill_name=target, is_fallback=False)
