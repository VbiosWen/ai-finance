"""图级集成——checkpointer 双轮记忆、动态技能 prompt、context_middleware 插槽顺位。"""
from __future__ import annotations

import asyncio
import unittest

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.conversation_agent import build_conversation_agent

RECEIVING = SkillConfig(name="receiving", description="收票", task_instructions="处理收票任务")
GENERAL = SkillConfig(name="general", description="通用", task_instructions="通用应答")
IDENTITY = AgentIdentity(persona="AI 账票助手", tones="专业简洁")


class _StubRecognizer:
    async def recognize(self, messages, skills):
        return IntentClassification(target_skill="receiving", confidence=0.9)


class _CaptureMiddleware(AgentMiddleware):
    """插槽探针:记录模型调用现场,并证明自身在路由之后执行。"""

    def __init__(self) -> None:
        super().__init__()
        self.model_calls: list[tuple[str, int, str | None]] = []
        self.before_agent_saw_skill: list[str | None] = []

    async def abefore_agent(self, state, runtime):
        self.before_agent_saw_skill.append(state.get("routed_skill"))
        return None

    async def awrap_model_call(self, request, handler):
        self.model_calls.append(
            (request.system_prompt, len(request.messages),
             request.state.get("routed_skill"))
        )
        return await handler(request)


def _build(capture: _CaptureMiddleware, checkpointer) -> object:
    model = GenericFakeChatModel(
        messages=iter([AIMessage(content="答一"), AIMessage(content="答二")])
    )
    return build_conversation_agent(
        llm=model,
        identity=IDENTITY,
        skills=[RECEIVING],
        general_skill=GENERAL,
        recognizer=_StubRecognizer(),
        policy=RoutingPolicy(RoutingConfig()),
        checkpointer=checkpointer,
        context_middleware=[capture],
    )


class ConversationAgentTest(unittest.TestCase):
    def test_two_turn_memory_and_dynamic_prompt(self) -> None:
        async def run() -> None:
            capture = _CaptureMiddleware()
            agent = _build(capture, MemorySaver())
            cfg = {"configurable": {"thread_id": "t-memory"}}

            await agent.ainvoke({"messages": [{"role": "user", "content": "录发票"}]}, cfg)
            r2 = await agent.ainvoke({"messages": [{"role": "user", "content": "继续"}]}, cfg)

            # 记忆生效:第二轮只喂 1 条,模型却看到 3 条(H,A,H 由 checkpointer 回放)
            self.assertEqual(capture.model_calls[1][1], 3)
            self.assertEqual(len(r2["messages"]), 4)
            # 动态技能 prompt:每次调用都换上 receiving 的渲染 prompt
            self.assertIn("处理收票任务", capture.model_calls[0][0])
            # 插槽顺位:capture 的 before_agent 在路由之后 → 已能看到裁决
            self.assertEqual(capture.before_agent_saw_skill, ["receiving", "receiving"])
            # 决策通道随 checkpoint 持久化
            self.assertEqual(r2.get("routed_skill"), "receiving")

        asyncio.run(run())

    def test_no_checkpointer_is_stateless(self) -> None:
        async def run() -> None:
            capture = _CaptureMiddleware()
            agent = _build(capture, None)
            await agent.ainvoke({"messages": [{"role": "user", "content": "一"}]})
            await agent.ainvoke({"messages": [{"role": "user", "content": "二"}]})
            # 无 checkpointer:两次模型调用各只见 1 条
            self.assertEqual([c[1] for c in capture.model_calls], [1, 1])

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
