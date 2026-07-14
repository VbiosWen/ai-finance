"""应用层端口（Ports）——定义应用层依赖的外部接口契约。

基础设施层实现这些端口，领域层不感知它们。

导出：
- AgentService: Agent 服务抽象端口
- LLMFactory: LLM 工厂抽象端口
"""
from application.ports.agent_service import AgentService
from application.ports.llm_factory import LLMFactory

__all__ = [
    "AgentService",
    "LLMFactory",
]
