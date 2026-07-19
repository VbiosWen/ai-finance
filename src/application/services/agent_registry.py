"""多技能 Agent 注册表 —— 分类器目录与可路由集合同源。"""
from __future__ import annotations

from application.ports.agent_service import AgentService
from domain.value_objects.skill_config import SkillConfig


class AgentRegistry:
    """skill_name → (SkillConfig, AgentService)。"""

    def __init__(
        self,
        entries: dict[str, tuple[SkillConfig, AgentService]],
        fallback: str,
    ) -> None:
        if fallback not in entries:  # fail-fast：兜底必须存在
            raise ValueError(f"兜底技能 '{fallback}' 未注册，无法启动")
        self._entries = entries
        self._fallback = fallback

    def get(self, skill_name: str) -> AgentService:
        entry = self._entries.get(skill_name) or self._entries[self._fallback]
        return entry[1]

    def available(self) -> set[str]:
        return set(self._entries.keys())

    def catalog(self) -> list[SkillConfig]:
        return [cfg for cfg, _ in self._entries.values()]
