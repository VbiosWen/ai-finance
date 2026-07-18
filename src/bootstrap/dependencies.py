"""FastAPI 依赖注入函数 —— 单一职责：从 app.state 获取预热好的依赖。

Repository 和 NacosClient 在 lifespan 中启动和预热，
路由通过 Depends(get_xxx) 直接从 app.state 获取，零延迟。
"""
from __future__ import annotations

import json
import logging

from fastapi import Depends, Request

from bootstrap.container import Container, build_container
from infrastructure.client.nacos import NacosClient
from infrastructure.config.llm_config import LLMConfig
from infrastructure.ports import (
    NacosAgentIdentityRepository,
    NacosSkillConfigRepository,
)

logger = logging.getLogger("ai-finance")


# ---------------------------------------------------------------------------
# 基础设施（lifespan 启动 + 预热，存 app.state）
# ---------------------------------------------------------------------------


def get_nacos_client(request: Request) -> NacosClient:
    """注入 NacosClient 单例。"""
    return request.app.state.nacos_client


def get_agent_identity_repo(request: Request) -> NacosAgentIdentityRepository:
    """注入已预热的 AgentIdentity 仓库。"""
    return request.app.state.agent_identity_repo


def get_skill_config_repo(request: Request) -> NacosSkillConfigRepository:
    """注入已预热的 SkillConfig 仓库。"""
    return request.app.state.skill_config_repo


# ---------------------------------------------------------------------------
# 业务依赖
# ---------------------------------------------------------------------------


async def get_llm_config(
    client: NacosClient = Depends(get_nacos_client),
) -> LLMConfig:
    """从 Nacos 加载 LLMConfig，不可用时降级到本地文件。"""
    raw = await client.get_config("llm-config", group="AI_FINANCE")
    if raw:
        logger.info("LLMConfig 来源: Nacos")
        return LLMConfig(**json.loads(raw))
    logger.info("LLMConfig 来源: 本地 config.json")
    return LLMConfig.load()


async def get_container(
    config: LLMConfig = Depends(get_llm_config),
) -> Container:
    """注入已装配的 Container。"""
    return await build_container(config=config)
