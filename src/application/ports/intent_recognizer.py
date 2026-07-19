"""意图识别端口 —— 输入对话 + 技能目录，输出结构化分类结果。"""
from __future__ import annotations

from typing import Protocol

from domain.value_objects.intent import IntentClassification
from domain.value_objects.skill_config import SkillConfig


class IntentRecognizer(Protocol):
    async def recognize(
        self,
        messages: list[dict[str, str]],
        skills: list[SkillConfig],
    ) -> IntentClassification:
        """识别当前对话最匹配的技能。基础设施层用 LLM 结构化输出实现。"""
        ...
