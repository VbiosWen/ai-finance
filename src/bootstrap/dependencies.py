"""FastAPI 依赖注入函数 —— 单一职责：从 app.state 获取预热好的依赖。

Repository 和 NacosClient 在 lifespan 中启动和预热，
路由通过 Depends(get_xxx) 直接从 app.state 获取，零延迟。
"""
from __future__ import annotations

import logging

from fastapi import Depends, Request

from bootstrap.container import Container, build_container
from infrastructure.client.nacos import NacosClient
from infrastructure.ports import (
    NacosAgentIdentityRepository,
    NacosSkillConfigRepository,
)
from infrastructure.client.database import DatabaseManager
from infrastructure.ports.data_base_config_nacos_repository import NacosPostgresConfigRepository
from infrastructure.ports.nacos_config_repository import NacosConfigRepository
from infrastructure.ports.nacos_llm_config_repository import NacosLLMConfigRepository

logger = logging.getLogger("ai-finance")


# ---------------------------------------------------------------------------
# 基础设施（lifespan 启动 + 预热，存 app.state）
# ---------------------------------------------------------------------------


def get_nacos_client(request: Request) -> NacosClient:
    """注入 NacosClient 单例。"""
    return request.app.state.nacos_client

def get_postgres_config_repo(request: Request) -> NacosPostgresConfigRepository:
    """注入已预热的 PostgreSQL 配置仓库。"""
    return request.app.state.postgres_config_repo


def get_db_manager(request: Request) -> DatabaseManager:
    """注入已初始化的数据库管理器。"""
    return request.app.state.db_manager

def get_agent_identity_repo(request: Request) -> NacosAgentIdentityRepository:
    """注入已预热的 AgentIdentity 仓库。"""
    return request.app.state.agent_identity_repo


def get_skill_config_repo(request: Request) -> NacosSkillConfigRepository:
    """注入已预热的 SkillConfig 仓库。"""
    return request.app.state.skill_config_repo

def get_llm_config_repo(request: Request) -> NacosLLMConfigRepository:
    """注入已预热的 LLM 配置仓库。"""
    return request.app.state.llm_config_repo


# ---------------------------------------------------------------------------
# 业务依赖
# ---------------------------------------------------------------------------


async def get_container(
    llm_repo: NacosLLMConfigRepository = Depends(get_llm_config_repo),
) -> Container:
    """注入已装配的 Container（LLMConfig 从预热的仓库获取）。"""
    return await build_container(config=llm_repo.get())

