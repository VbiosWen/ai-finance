"""组合根：集中装配各层依赖。

负责：
- 将已加载的 LLMConfig、Prompt、Tools 装配为可运行的 Agent
- 组装为 Container 供 interfaces 层取用

配置加载由调用方（如 FastAPI lifespan）在调用 build_container 之前完成。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from domain.shared.ai_tools import AITool
from domain.shared.prompts import DEFAULT_AGENT_PROMPT, Prompt
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.tool_adapter import adapt_ai_tools
from infrastructure.config.database import create_db_engine
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

    # 基础设施
    db_engine: AsyncEngine | None = None

    # 随业务接入扩展，例如：
    #   invoice_repository: "InvoiceRepository"
    #   message_bus: "MessageBus"


async def build_container(
    *,
    config: LLMConfig | None = None,
    system_prompt: Prompt | None = None,
    tools: list[AITool] | None = None,
    db_url: str | None = None,
    skip_ai: bool = False,
    skip_db: bool = False,
) -> Container:
    """构建并返回组合根容器。

    Args:
        config: LLM 配置（由调用方提前加载）。
                ``skip_ai=True`` 时可为 None。
        system_prompt: 系统提示词值对象，默认使用 DEFAULT_AGENT_PROMPT。
        tools: 领域工具实例列表。
        db_url: PostgreSQL 连接字符串，为 None 时从环境变量 DATABASE_URL 读取。
        skip_ai: 跳过 AI 组件装配，返回最小容器（用于测试）。
        skip_db: 跳过数据库引擎创建（用于测试）。

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
        container.db_engine = create_db_engine(url=db_url)

    # 1. LLM
    llm_factory = LLMClientFactory(config)
    llm: Any = llm_factory.create_llm
    container.llm_factory = llm_factory

    # 2. 系统提示词
    prompt = system_prompt or DEFAULT_AGENT_PROMPT
    logger.info("使用系统提示词: name=%s, version=%s", prompt.name, prompt.version)

    # 3. 领域工具 → LangChain Tool
    domain_tools = tools or []
    lc_tools = adapt_ai_tools(domain_tools)
    logger.info("已适配 %d 个领域工具", len(lc_tools))
    container.tools = domain_tools

    # 4. 创建 ReAct Agent
    agent = create_react_agent(
        llm=llm,
        tools=lc_tools,
        system_prompt=prompt.system_text,
    )

    # 5. 包装为 AgentService
    container.agent_service = LangChainAgentService(agent)

    logger.info("组合根装配完成: model=%s, 工具数=%d", config.model, len(lc_tools))
    return container
