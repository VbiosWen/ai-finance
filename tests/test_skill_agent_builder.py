"""build_agent_registry 测试——建出每技能 Agent + 兜底 general，断言结构。"""
from __future__ import annotations

import unittest

from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.skill_agent_builder import build_agent_registry
from infrastructure.config.llm_config import LLMConfig
from infrastructure.ai.llm_client_factory import LLMClientFactory


def _identity() -> AgentIdentity:
    return AgentIdentity(persona="账票助手", tones="专业简洁")


def _skills() -> list[SkillConfig]:
    return [
        SkillConfig(name="auditing", description="发票稽核", task_instructions="稽核"),
        SkillConfig(name="receiving", description="发票收票", task_instructions="收票"),
    ]


class BuildAgentRegistryTest(unittest.TestCase):
    def test_registry_has_all_skills_plus_general(self) -> None:
        # 假 key，仅构建 ChatDeepSeek 与编译图，不发起网络调用
        factory = LLMClientFactory(LLMConfig(model="deepseek-chat", api_key="sk-test"))
        registry = build_agent_registry(
            identity=_identity(),
            skills=_skills(),
            general_skill=GENERAL_SKILL,
            llm_factory=factory,
        )
        self.assertEqual(registry.available(), {"auditing", "receiving", "general"})
        # 兜底存在：get 未知技能回落 general，不抛错
        self.assertIsNotNone(registry.get("不存在"))


if __name__ == "__main__":
    unittest.main()
