"""技能子 Agent 工厂 —— 按 Skill 动态编译独立的 LangGraph Agent。

每个 Skill 拥有专属的 tools 列表和完整的系统 prompt，
通过 ToolRegistry 动态解析工具依赖，延迟编译并缓存。
"""

from __future__ import annotations

import logging
from typing import Any

from domain.tools.tool_registry import ToolRegistry
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.agent_prompt_config import AgentPromptConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.tool_adapter import adapt_ai_tools

logger = logging.getLogger("ai-finance")


class SkillAgentFactory:
    """为每个 Skill 编译并缓存独立的 LangGraph Agent。

    缓存的 agent 可直接执行，无需每次重建。当 SkillConfig 热更新时，
    调用 ``invalidate(skill_name)`` 使缓存失效。

    用法::

        factory = SkillAgentFactory(llm, registry, identity)
        agent = factory.build(skill)          # 或 factory.get_or_build(name, repo)
        result = await agent.ainvoke({"messages": [...]})
    """

    def __init__(
        self,
        llm: Any,
        tool_registry: ToolRegistry,
        agent_identity: AgentIdentity,
    ) -> None:
        """初始化工厂。

        Args:
            llm: LangChain BaseChatModel 实例（ChatOpenAI / ChatAnthropic 等）。
            tool_registry: 全局工具注册表，按名称解析 AITool。
            agent_identity: Agent 身份定义（所有子 Agent 共享）。
        """
        self._llm = llm
        self._registry = tool_registry
        self._identity = agent_identity
        self._agents: dict[str, Any] = {}
        """skill_name → 编译后的 LangGraph agent"""

    # ── 编译 ──────────────────────────────────────────────────────

    def build(self, skill: SkillConfig) -> Any:
        """为一个 Skill 编译专属 LangGraph Agent。

        解析 skill.tool_names → 从 ToolRegistry 获取 AITool 实例 →
        适配为 LangChain Tool → 创建内嵌模式的 prompt → 编译 agent。

        Args:
            skill: 技能完整配置。

        Returns:
            编译后的 LangGraph agent（可直接 ainvoke/astream）。

        Raises:
            KeyError: skill.tool_names 中有未注册的工具。
        """
        # 命中缓存
        cache_key = f"{skill.name}:{skill.version}"
        if cache_key in self._agents:
            logger.debug("命中 Skill Agent 缓存: %s", cache_key)
            return self._agents[cache_key]

        # 动态解析工具
        domain_tools = self._registry.resolve(skill.tool_names)
        lc_tools = adapt_ai_tools(domain_tools)

        # 内嵌模式 prompt（子 Agent 仅一个技能，token 可控）
        prompt = AgentPromptConfig(
            agent_identity=self._identity,
            skill=[skill],
        ).render()

        # 编译
        agent = create_react_agent(
            llm=self._llm,
            tools=lc_tools,
            system_prompt=prompt,
        )

        self._agents[cache_key] = agent
        logger.info(
            "Skill Agent 已编译: skill=%s version=%s tools=%d",
            skill.name,
            skill.version,
            len(domain_tools),
        )
        return agent

    # ── 查询 ──────────────────────────────────────────────────────

    def get_or_build(
        self,
        skill_name: str,
        skill_repo,  # SkillConfigRepository
        *,
        config_key: str = "skill-configs",
    ) -> Any:
        """按技能名获取或编译 Agent。

        Args:
            skill_name: 技能名称（对应 SkillConfig.name）。
            skill_repo: SkillConfigRepository 实例。
            config_key: 仓储中的配置 key。

        Returns:
            编译后的 LangGraph agent。

        Raises:
            KeyError: 技能名在配置列表中不存在。
        """
        skills = skill_repo.get(config_key)
        for skill in skills:
            if skill.name == skill_name:
                return self.build(skill)
        raise KeyError(f"技能 '{skill_name}' 未在配置中找到")

    # ── 缓存管理 ──────────────────────────────────────────────────

    def invalidate(self, skill_name: str | None = None) -> int:
        """使缓存失效。

        Args:
            skill_name: 为 None 时清空全部缓存；否则仅清空指定技能的缓存。

        Returns:
            失效的 agent 数量。
        """
        if skill_name is None:
            count = len(self._agents)
            self._agents.clear()
            logger.info("Skill Agent 缓存已全部清空（%d 个）", count)
            return count

        removed = sum(
            1 for k in list(self._agents) if k.startswith(f"{skill_name}:")
        )
        self._agents = {
            k: v for k, v in self._agents.items()
            if not k.startswith(f"{skill_name}:")
        }
        logger.info("Skill Agent 缓存已失效: skill=%s（%d 个）", skill_name, removed)
        return removed
