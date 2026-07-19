"""组合根：集中装配各层依赖。

支持两种 Agent 装配模式：

- **内嵌模式**（兼容）：tools + system_prompt 直接编译为单个 Agent。
- **动态模式**（推荐）：传入 ``agent_entity`` + ``skill_repo`` + ``tool_registry``，
  构建 Router Agent（含 SkillLookupTool + DispatchToSkillTool），
  子 Agent 按需动态编译，实现按技能的工具隔离与注入。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from domain.entities.agent_entity import AgentEntity
from domain.ports.skill_config_repository import SkillConfigRepository
from domain.shared.ai_tools import AITool
from domain.shared.prompts import DEFAULT_AGENT_PROMPT, Prompt
from domain.tools.tool_registry import ToolRegistry
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.dispatch_tool import DispatchToSkillTool
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.skill_agent_factory import SkillAgentFactory
from infrastructure.ai.tool_adapter import adapt_ai_tools
from infrastructure.config.llm_config import LLMConfig
from interfaces.ai.react_agent import LangChainAgentService

logger = logging.getLogger("ai-finance")


@dataclass
class Container:
    """持有已装配好的依赖，供 interfaces 与启动流程取用。"""

    # AI
    agent_service: LangChainAgentService | None = None
    llm_factory: LLMClientFactory | None = None
    tools: list[AITool] = field(default_factory=list)

    # 动态技能（仅 router 模式下填充）
    skill_agent_factory: SkillAgentFactory | None = None
    tool_registry: ToolRegistry | None = None

    # 基础设施
    db_engine: Any | None = None


async def build_container(
    *,
    config: LLMConfig | None = None,
    system_prompt: Prompt | None = None,
    tools: list[AITool] | None = None,
    # ── 动态 skill 模式参数 ──────────────────────────────────
    agent_entity: AgentEntity | None = None,
    skill_repo: SkillConfigRepository | None = None,
    tool_registry: ToolRegistry | None = None,
    # ── 基础设施 ─────────────────────────────────────────────
    db_url: str | None = None,
    skip_ai: bool = False,
    skip_db: bool = False,
) -> Container:
    """构建并返回组合根容器。

    两种模式：
    1. **内嵌模式**（传统）: 传入 ``config`` + ``system_prompt`` + ``tools``，
       所有 skill 指令嵌入 prompt，所有 tool 共享。
    2. **动态模式**（推荐）: 传入 ``config`` + ``agent_entity`` +
       ``skill_repo`` + ``tool_registry``，构建 Router Agent，
       子 Agent 按技能动态编译并持有专属 tools。

    Args:
        config: LLM 配置。skip_ai=True 时可为 None。
        system_prompt: 系统提示词（内嵌模式）。
        tools: 领域工具列表（内嵌模式）。
        agent_entity: Agent 聚合根（动态模式，含 prompt_config + base tools）。
        skill_repo: 技能配置仓储（动态模式）。
        tool_registry: 全局工具注册表（动态模式）。
        db_url: PostgreSQL 连接字符串。
        skip_ai: 跳过 AI 组件装配。
        skip_db: 跳过数据库引擎创建。

    Returns:
        装配完成的 Container 实例。
    """
    if skip_ai:
        logger.info("跳过 AI 组件装配，返回最小容器")
        return Container()

    if config is None:
        raise ValueError("非 skip_ai 模式下必须提供 config 参数")

    container = Container()

    # 0. 数据库引擎
    if not skip_db:
        from infrastructure.client.database import create_db_engine
        container.db_engine = create_db_engine(url=db_url)

    # 1. LLM
    llm_factory = LLMClientFactory(config)
    llm: Any = llm_factory.create_llm
    container.llm_factory = llm_factory

    # ── 模式判断 ──────────────────────────────────────────────────
    use_router = (
        agent_entity is not None
        and agent_entity.prompt_config.skill_refs
        and skill_repo is not None
        and tool_registry is not None
    )

    if use_router:
        # ============================================================
        # 动态模式：Router Agent
        # ============================================================
        logger.info("使用动态 Skill 路由模式")

        # 2. 技能子 Agent 工厂
        skill_factory = SkillAgentFactory(
            llm=llm,
            tool_registry=tool_registry,
            agent_identity=agent_entity.prompt_config.agent_identity,
        )
        container.skill_agent_factory = skill_factory
        container.tool_registry = tool_registry

        # 3. Router 的工具链
        #    SkillLookupTool 由 AgentEntity.build_tools() 自动注入
        router_tools = agent_entity.build_tools(skill_repo)
        #    加上 DispatchToSkillTool（分派到子 Agent）
        router_tools.append(DispatchToSkillTool(skill_factory, skill_repo))

        # 4. Router 的系统提示词（仅含技能菜单）
        router_prompt = agent_entity.render_prompt()

        # 5. 编译 Router Agent
        lc_tools = adapt_ai_tools(router_tools)
        agent = create_react_agent(
            llm=llm,
            tools=lc_tools,
            system_prompt=router_prompt,
        )

        container.tools = router_tools
        container.agent_service = LangChainAgentService(agent)

        logger.info(
            "Router Agent 装配完成: skills=%d tools=%d",
            len(agent_entity.prompt_config.skill_refs),
            len(lc_tools),
        )
    else:
        # ============================================================
        # 内嵌模式：传统单 Agent
        # ============================================================
        logger.info("使用内嵌模式")

        # 2. 系统提示词
        prompt_text: str
        if agent_entity is not None:
            prompt_text = agent_entity.render_prompt()
            domain_tools = agent_entity.build_tools(skill_repo) if skill_repo else list(agent_entity.tools)
        else:
            prompt = system_prompt or DEFAULT_AGENT_PROMPT
            prompt_text = prompt.system_text
            domain_tools = tools or []

        # 3. 领域工具 → LangChain Tool
        lc_tools = adapt_ai_tools(domain_tools)
        container.tools = domain_tools

        # 4. 编译 Agent
        agent = create_react_agent(
            llm=llm,
            tools=lc_tools,
            system_prompt=prompt_text,
        )

        container.agent_service = LangChainAgentService(agent)

        logger.info(
            "Agent 装配完成: model=%s tools=%d", config.model, len(lc_tools)
        )

    return container
