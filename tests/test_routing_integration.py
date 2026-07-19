"""路由端到端集成——首帧 routing、兜底、分类器故障降级仍 200。"""
from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator

import httpx

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.services.agent_registry import AgentRegistry
from application.services.routing_agent_service import RoutingAgentService
from bootstrap.app import create_app
from domain.services.routing_policy import RoutingPolicy
from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from interfaces.api.dependencies import get_agent_service
from tests.support import make_stub_container


class _StubWorker:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=self.tag)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="token", content=self.tag)
        yield AgentStreamEvent(event_type="done")


class _StubRecognizer:
    def __init__(self, result, *, raise_exc=False) -> None:
        self._result, self._raise = result, raise_exc

    async def recognize(self, messages, skills) -> IntentClassification:
        if self._raise:
            raise RuntimeError("炸")
        return self._result


def _routing_service(recognizer) -> RoutingAgentService:
    registry = AgentRegistry(
        {
            "auditing": (SkillConfig(name="auditing", description="稽核", task_instructions="稽核"), _StubWorker("auditing")),
            "general": (GENERAL_SKILL, _StubWorker("general")),
        },
        fallback="general",
    )
    return RoutingAgentService(recognizer, RoutingPolicy(RoutingConfig()), registry)


async def _stream_events(client) -> list[str]:
    types: list[str] = []
    async with client.stream("POST", "/agent/chat/stream", json={"messages": [{"role": "user", "content": "帮我稽核"}]}) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                types.append(line.split(":", 1)[1].strip())
    return types


class RoutingIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.app = create_app(make_stub_container())

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_first_frame_is_routing(self) -> None:
        recognizer = _StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.9))
        self.app.dependency_overrides[get_agent_service] = lambda: _routing_service(recognizer)

        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                types = await _stream_events(client)
                self.assertEqual(types[0], "routing")
                self.assertIn("done", types)

        asyncio.run(run())

    def test_classifier_failure_still_200_and_degrades(self) -> None:
        recognizer = _StubRecognizer(None, raise_exc=True)
        self.app.dependency_overrides[get_agent_service] = lambda: _routing_service(recognizer)

        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                types = await _stream_events(client)
                self.assertEqual(types[0], "routing")  # 降级仍先发 routing（general）

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
