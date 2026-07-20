"""RoutingMiddleware 测试——决策写 state、异常/低置信兜底、prompt 选择、窗口裁剪。"""
from __future__ import annotations

import asyncio
import unittest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.middleware.routing import RoutingMiddleware, _to_dict_messages

RECEIVING = SkillConfig(name="receiving", description="收票", task_instructions="处理收票任务")
GENERAL = SkillConfig(name="general", description="通用", task_instructions="通用应答")
IDENTITY = AgentIdentity(persona="AI 账票助手", tones="专业简洁")


class _StubRecognizer:
    """可注入结果或异常的识别器桩;记录收到的消息以断言窗口裁剪。"""

    def __init__(self, result=None, error=None) -> None:
        self.result, self.error = result, error
        self.seen: list[dict[str, str]] | None = None

    async def recognize(self, messages, skills):
        self.seen = messages
        if self.error:
            raise self.error
        return self.result


def _middleware(recognizer, window: int = 8) -> RoutingMiddleware:
    return RoutingMiddleware(
        recognizer=recognizer,
        policy=RoutingPolicy(RoutingConfig()),
        identity=IDENTITY,
        skills=[RECEIVING],
        general_skill=GENERAL,
        recognizer_window=window,
    )


class BeforeAgentTest(unittest.TestCase):
    def test_writes_decision_into_state(self) -> None:
        stub = _StubRecognizer(IntentClassification(target_skill="receiving", confidence=0.9))
        update = asyncio.run(_middleware(stub).abefore_agent(
            {"messages": [HumanMessage(content="录一张发票")]}, None
        ))
        self.assertEqual(update["routed_skill"], "receiving")
        self.assertFalse(update["routing_fallback"])
        self.assertAlmostEqual(update["routing_confidence"], 0.9)

    def test_recognizer_error_falls_back(self) -> None:
        stub = _StubRecognizer(error=RuntimeError("llm down"))
        update = asyncio.run(_middleware(stub).abefore_agent(
            {"messages": [HumanMessage(content="继续")]}, None
        ))
        self.assertEqual(update["routed_skill"], "general")
        self.assertTrue(update["routing_fallback"])

    def test_low_confidence_falls_back(self) -> None:
        # RoutingConfig 默认阈值 0.6,置信 0.3 → 兜底
        stub = _StubRecognizer(IntentClassification(target_skill="receiving", confidence=0.3))
        update = asyncio.run(_middleware(stub).abefore_agent(
            {"messages": [HumanMessage(content="嗯")]}, None
        ))
        self.assertEqual(update["routed_skill"], "general")
        self.assertTrue(update["routing_fallback"])

    def test_recognizer_sees_tail_window_as_dicts(self) -> None:
        stub = _StubRecognizer(IntentClassification(target_skill=None, confidence=0.0))
        msgs = [SystemMessage(content="系统提示")]
        for i in range(6):
            msgs.append(HumanMessage(content=f"问{i}"))
            msgs.append(AIMessage(content=f"答{i}"))
        asyncio.run(_middleware(stub, window=4).abefore_agent({"messages": msgs}, None))
        self.assertEqual(len(stub.seen), 4)  # 只取尾部 4 条
        self.assertEqual(stub.seen[-1], {"role": "assistant", "content": "答5"})
        self.assertTrue(all(m["role"] in ("user", "assistant") for m in stub.seen))


class MessageConversionTest(unittest.TestCase):
    def test_system_and_empty_skipped(self) -> None:
        msgs = [SystemMessage(content="s"), HumanMessage(content=""), HumanMessage(content="q")]
        self.assertEqual(_to_dict_messages(msgs, 8), [{"role": "user", "content": "q"}])


class PromptSelectionTest(unittest.TestCase):
    def test_prompt_for_skill_and_fallbacks(self) -> None:
        mw = _middleware(_StubRecognizer())
        self.assertIn("处理收票任务", mw.prompt_for("receiving"))
        self.assertIn("通用应答", mw.prompt_for(None))       # 未裁决 → 兜底
        self.assertIn("通用应答", mw.prompt_for("unknown"))  # 未知技能 → 兜底


if __name__ == "__main__":
    unittest.main()
