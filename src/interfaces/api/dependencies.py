"""FastAPI 依赖注入 provider——从 app.state.container 取已装配依赖。

签名只标 domain / application 端口类型;函数体经 app.state(无类型)取容器字段,
不产生对 bootstrap / infrastructure 的 import,依赖方向保持 interfaces → application → domain。
"""
from __future__ import annotations

from fastapi import HTTPException, Request

from application.ports.agent_service import AgentService
from domain.ports.agent_identity_repository import AgentIdentityRepository
from domain.ports.skill_config_repository import SkillConfigRepository


def get_agent_identity_repo(request: Request) -> AgentIdentityRepository:
    """注入 AgentIdentity 配置仓库(lifespan 已预热)。"""
    return request.app.state.container.agent_identity_repo


def get_skill_config_repo(request: Request) -> SkillConfigRepository:
    """注入 SkillConfig 配置仓库(lifespan 已预热)。"""
    return request.app.state.container.skill_config_repo


def get_agent_service(request: Request) -> AgentService:
    """注入 lifespan 预热的 AgentService 单例。

    单例常驻使 MemorySaver 跨请求存活，thread_id 多轮记忆才能生效。
    """
    agent_service = getattr(request.app.state.container, "agent_service", None)
    if agent_service is None:
        raise HTTPException(status_code=503, detail="AgentService 尚未就绪")
    return agent_service
