"""AgentRegistry 测试——get/available/catalog、缺失兜底、无兜底抛错。"""
from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.services.agent_registry import AgentRegistry
from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.skill_config import SkillConfig


class _StubService:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=self.tag)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="done")


def _skill(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=f"{name} 技能", task_instructions="做事")


def _registry() -> AgentRegistry:
    entries = {
        "auditing": (_skill("auditing"), _StubService("auditing")),
        "general": (GENERAL_SKILL, _StubService("general")),
    }
    return AgentRegistry(entries, fallback="general")


class AgentRegistryTest(unittest.TestCase):
    def test_general_skill_name(self) -> None:
        self.assertEqual(GENERAL_SKILL.name, "general")

    def test_get_hit(self) -> None:
        self.assertEqual(_registry().get("auditing").tag, "auditing")

    def test_get_missing_returns_fallback(self) -> None:
        self.assertEqual(_registry().get("不存在").tag, "general")

    def test_available(self) -> None:
        self.assertEqual(_registry().available(), {"auditing", "general"})

    def test_catalog_contains_skill_configs(self) -> None:
        names = {s.name for s in _registry().catalog()}
        self.assertEqual(names, {"auditing", "general"})

    def test_missing_fallback_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentRegistry({"auditing": (_skill("auditing"), _StubService("a"))}, fallback="general")


if __name__ == "__main__":
    unittest.main()
