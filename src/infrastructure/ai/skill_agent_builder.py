"""多技能 Agent 装配 —— 从 SkillConfig 列表建「每技能一个 Agent」+ 兜底 general。"""
from __future__ import annotations

import logging

from application.ports.agent_service import AgentService
from application.services.agent_registry import AgentRegistry
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.agent_prompt_config import AgentPromptConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.react_agent import LangChainAgentService

logger = logging.getLogger("ai-finance")


def _build_one(identity: AgentIdentity, skill: SkillConfig, llm) -> AgentService:
    """把单个技能装配为一个可运行的 AgentService。"""
    prompt = AgentPromptConfig(agent_identity=identity, skill=[skill]).render()
    agent = create_react_agent(llm=llm, tools=[], system_prompt=prompt, enable_memory=False)
    return LangChainAgentService(agent)


def build_agent_registry(
    *,
    identity: AgentIdentity,
    skills: list[SkillConfig],
    general_skill: SkillConfig,
    llm_factory: LLMClientFactory,
) -> AgentRegistry:
    """遍历技能建 Agent，再建兜底 general，装进 AgentRegistry。"""
    llm = llm_factory.create_llm()
    entries: dict[str, tuple[SkillConfig, AgentService]] = {}
    for skill in skills:
        entries[skill.name] = (skill, _build_one(identity, skill, llm))
    entries[general_skill.name] = (general_skill, _build_one(identity, general_skill, llm))
    logger.info("已装配 %d 个技能 Agent（含兜底 %s）", len(entries), general_skill.name)
    return AgentRegistry(entries, fallback=general_skill.name)
