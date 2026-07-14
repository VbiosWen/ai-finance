"""AI 基础设施——LangChain ReAct Agent 的出站适配器实现。

包含：
- agent_factory: 封装 create_agent 创建 ReAct Agent。
- tool_adapter: 将领域 AITool 适配为 LangChain Tool。
- llm_client: LLM provider 工厂（OpenAI / Anthropic）。
"""
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.tool_adapter import adapt_ai_tool, adapt_ai_tools

__all__ = [
    "LLMClientFactory",
    "adapt_ai_tool",
    "adapt_ai_tools",
    "create_react_agent",
]
