"""RoutingAgentService 测试——路由分发、routing 首帧、失败降级、run 回填。"""
from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.services.agent_registry import AgentRegistry
from application.services.routing_agent_service import RoutingAgentService
from domain.services.routing_policy import RoutingPolicy
from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig


class _StubWorker:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=self.tag)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="token", content=self.tag)
        yield AgentStreamEvent(event_type="done")


class _StubRecognizer:
    def __init__(self, result: IntentClassification | None, *, raise_exc: bool = False) -> None:
        self._result = result
        self._raise = raise_exc

    async def recognize(self, messages, skills) -> IntentClassification:
        if self._raise:
            raise RuntimeError("分类器炸了")
        return self._result


def _skill(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=f"{name} 技能", task_instructions="做事")


def _service(recognizer: _StubRecognizer) -> RoutingAgentService:
    registry = AgentRegistry(
        {
            "auditing": (_skill("auditing"), _StubWorker("auditing")),
            "general": (GENERAL_SKILL, _StubWorker("general")),
        },
        fallback="general",
    )
    policy = RoutingPolicy(RoutingConfig())
    return RoutingAgentService(recognizer, policy, registry)


class RoutingAgentServiceTest(unittest.TestCase):
    def test_routes_to_matched_worker(self) -> None:
        svc = _service(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.9)))
        resp = asyncio.run(svc.run(AgentRequest(messages=[{"role": "user", "content": "帮我稽核"}])))
        self.assertEqual(resp.reply, "auditing")
        self.assertEqual(resp.routed_skill, "auditing")

    def test_stream_emits_routing_first(self) -> None:
        svc = _service(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.9)))

        async def collect() -> list[AgentStreamEvent]:
            return [ev async for ev in svc.stream(AgentRequest(messages=[{"role": "user", "content": "x"}]))]

        events = asyncio.run(collect())
        self.assertEqual(events[0].event_type, "routing")
        self.assertEqual(events[0].skill_name, "auditing")
        self.assertEqual(events[1].event_type, "token")
        self.assertEqual(events[1].content, "auditing")

    def test_low_confidence_falls_back_to_general(self) -> None:
        svc = _service(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.2)))
        resp = asyncio.run(svc.run(AgentRequest(messages=[{"role": "user", "content": "闲聊"}])))
        self.assertEqual(resp.routed_skill, "general")

    def test_recognizer_failure_degrades_to_general(self) -> None:
        svc = _service(_StubRecognizer(None, raise_exc=True))
        resp = asyncio.run(svc.run(AgentRequest(messages=[{"role": "user", "content": "x"}])))
        self.assertEqual(resp.reply, "general")
        self.assertEqual(resp.routed_skill, "general")


if __name__ == "__main__":
    unittest.main()
