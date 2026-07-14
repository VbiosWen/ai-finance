"""组合根：集中装配各层依赖。

负责：
- 创建基础设施（LLM 工厂、Agent 工厂、工具适配器）
- 用 infrastructure 的实现装配 domain 定义的端口接口
- 组装为 Container 供 interfaces 层取用
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from domain.shared.ai_tools import AITool
from domain.shared.prompts import DEFAULT_AGENT_PROMPT, Prompt
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client import LLMClientFactory
from infrastructure.ai.tool_adapter import adapt_ai_tools
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
    provider: str | None = None,
    system_prompt: Prompt | None = None,
    tools: list[AITool] | None = None,
    temperature: float = 0.1,
    max_tokens: int | None = None,
    skip_ai: bool = False,
) -> Container:
    """构建并返回组合根容器。

    装配链路：
    1. 创建 LLMClientFactory → 生成 BaseChatModel
    2. 加载系统提示词
    3. 收集领域工具 → 适配为 LangChain Tool
    4. create_react_agent 创建 LangGraph Agent
    5. 包装为 LangChainAgentService（实现 AgentService 端口）

    Args:
        provider: LLM provider（"openai" 或 "anthropic"），默认取环境变量。
        system_prompt: 系统提示词值对象，默认使用 DEFAULT_AGENT_PROMPT。
        tools: 领域工具实例列表。
        temperature: LLM 温度参数。
        max_tokens: 最大输出 token 数。
        skip_ai: 跳过 AI 组件装配，返回最小容器（用于测试或非 AI 场景）。

    Returns:
        装配完成的 Container 实例。
    """
    if skip_ai:
        logger.info("跳过 AI 组件装配，返回最小容器")
        return Container()

    container = Container()

    # 1. LLM 工厂
    try:
        llm_factory = LLMClientFactory(provider=provider)
        llm = llm_factory.create_chat_model(
            temperature=temperature,
            max_tokens=max_tokens,
        )
        container.llm_factory = llm_factory
    except (RuntimeError, ValueError) as exc:
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

    logger.info("组合根装配完成: LLM=%s, 工具数=%d", llm_factory.provider, len(lc_tools))
    return container
