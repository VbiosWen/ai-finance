"""LlmIntentRecognizer 测试——prompt 拼装 + 结构化输出解析（假 LLM）。"""
from __future__ import annotations

import asyncio
import unittest

from domain.value_objects.intent import IntentClassification
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.llm_intent_recognizer import (
    LlmIntentRecognizer,
    _build_classify_prompt,
)


class _FakeStructured:
    def __init__(self, result: IntentClassification) -> None:
        self._result = result
        self.last_prompt: str | None = None

    async def ainvoke(self, prompt: str) -> IntentClassification:
        self.last_prompt = prompt
        return self._result


class _FakeLLM:
    def __init__(self, result: IntentClassification) -> None:
        self._structured = _FakeStructured(result)

    def with_structured_output(self, schema: type) -> _FakeStructured:
        return self._structured


def _skills() -> list[SkillConfig]:
    return [
        SkillConfig(name="auditing", description="发票稽核与合规校验", task_instructions="稽核"),
        SkillConfig(name="receiving", description="发票收票与信息提取", task_instructions="收票"),
    ]


class BuildPromptTest(unittest.TestCase):
    def test_prompt_contains_each_skill(self) -> None:
        catalog = "\n".join(f"- {s.name}: {s.description}" for s in _skills())
        prompt = _build_classify_prompt(catalog, [{"role": "user", "content": "帮我稽核发票"}])
        self.assertIn("auditing", prompt)
        self.assertIn("发票稽核与合规校验", prompt)
        self.assertIn("receiving", prompt)
        self.assertIn("帮我稽核发票", prompt)


class RecognizeTest(unittest.TestCase):
    def test_recognize_returns_structured_result(self) -> None:
        expected = IntentClassification(target_skill="auditing", confidence=0.88, reason="含稽核意图")
        llm = _FakeLLM(expected)
        rec = LlmIntentRecognizer(llm)
        result = asyncio.run(rec.recognize([{"role": "user", "content": "帮我稽核发票"}], _skills()))
        self.assertEqual(result.target_skill, "auditing")
        self.assertIn("auditing: 发票稽核与合规校验", llm._structured.last_prompt)


if __name__ == "__main__":
    unittest.main()
