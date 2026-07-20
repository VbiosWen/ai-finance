"""Agent 图中间件——路由与上下文工程扩展点的家。

新增上下文工程策略(压缩/规划)= 实现 langchain 的 AgentMiddleware 放本包,
经 build_conversation_agent(context_middleware=[...]) 插槽注入。
"""
from infrastructure.ai.middleware.routing import RoutingMiddleware, RoutingState

__all__ = ["RoutingMiddleware", "RoutingState"]
