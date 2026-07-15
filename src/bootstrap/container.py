"""组合根：集中装配各层依赖。

负责：
- 创建基础设施（LLM 工厂、Agent 工厂、工具适配器）
- 用 infrastructure 的实现装配 domain 定义的端口接口
- 组装为 Container 供 interfaces 层取用
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from domain.shared.ai_tools import AITool
from domain.shared.prompts import DEFAULT_AGENT_PROMPT, Prompt
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.tool_adapter import adapt_ai_tools
from infrastructure.config.llm_config import LLMConfig
from interfaces.ai.react_agent import LangChainAgentService

logger = logging.getLogger("ai-finance")


@dataclass
class Container:
    """持有已装配好的依赖，供 interfaces 与启动流程取用。"""

    # AI 相关
    agent_service: LangChainAgentService | None = None
    llm_factory: LLMClientFactory | None = None
    tools: list[AITool] = field(default_factory=list)

    # 随业务接入，例如：
    #   invoice_repository: "InvoiceRepository"
    #   message_bus: "MessageBus"


def build_container(
    *,
    config: LLMConfig | None = None,
    system_prompt: Prompt | None = None,
    tools: list[AITool] | None = None,
    skip_ai: bool = False,
) -> Container:
    """构建并返回组合根容器。

    装配链路：
    1. 根据 LLMConfig 创建 LLM 实例
    2. 加载系统提示词
    3. 收集领域工具 → 适配为 LangChain Tool
    4. create_react_agent 创建 LangGraph Agent
    5. 包装为 LangChainAgentService（实现 AgentService 端口）

    Args:
        config: LLM 配置对象。为 None 时尝试从 config/config.json 加载。
        system_prompt: 系统提示词值对象，默认使用 DEFAULT_AGENT_PROMPT。
        tools: 领域工具实例列表。
        skip_ai: 跳过 AI 组件装配，返回最小容器（用于测试或非 AI 场景）。

    Returns:
        装配完成的 Container 实例。
    """
    if skip_ai:
        logger.info("跳过 AI 组件装配，返回最小容器")
        return Container()

    container = Container()

    # 1. LLM
    try:
        if config is None:
            config = LLMConfig.from_json("config/config.json")
        llm_factory = LLMClientFactory(config)
        llm: Any = llm_factory.create_llm
        container.llm_factory = llm_factory
    except (ValueError, FileNotFoundError) as exc:
        logger.warning("无法创建 LLM: %s，AI 功能将不可用", exc)
        return container

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
