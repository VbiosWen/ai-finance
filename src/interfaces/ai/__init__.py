"""AI 用户接口层——AI Agent 的入站适配器。

将 LangChain agent 包装为应用层 AgentService 端口实现，
供 FastAPI 路由等上层调用。
"""
from interfaces.ai.react_agent import LangChainAgentService

__all__ = [
    "LangChainAgentService",
]
