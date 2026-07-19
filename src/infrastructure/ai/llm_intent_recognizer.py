"""基于 LLM 结构化输出的意图识别器 —— 实现 IntentRecognizer 端口。

单次 with_structured_output 调用，不是 ReAct agent，更快更省。
IntentClassification 是纯 Pydantic 值对象，其 schema 在基础设施层被读取，
领域层保持洁净。
"""
from __future__ import annotations

import logging
from typing import Any

from domain.value_objects.intent import IntentClassification
from domain.value_objects.skill_config import SkillConfig

logger = logging.getLogger("ai-finance")


def _build_classify_prompt(catalog: str, messages: list[dict[str, str]]) -> str:
    """拼装分类 prompt：列技能目录 + 要求择一 + 允许 None。"""
    conversation = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
    return (
        "你是账票服务的意图识别器。下面是可用技能目录（名称: 简介）：\n"
        f"{catalog}\n\n"
        "根据以下对话，判断用户最匹配哪一个技能。\n"
        f"对话：\n{conversation}\n\n"
        "只输出结构化结果：最匹配的技能名 target_skill（无法归类则为 null）、"
        "置信度 confidence（0~1）、简短理由 reason。"
    )


class LlmIntentRecognizer:
    """实现 IntentRecognizer 端口。"""

    def __init__(self, llm: Any) -> None:
        self._structured = llm.with_structured_output(IntentClassification)

    async def recognize(
        self,
        messages: list[dict[str, str]],
        skills: list[SkillConfig],
    ) -> IntentClassification:
        catalog = "\n".join(f"- {s.name}: {s.description}" for s in skills)
        prompt = _build_classify_prompt(catalog, messages)
        result: IntentClassification = await self._structured.ainvoke(prompt)
        return result
