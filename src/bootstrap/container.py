"""组合根:集中装配各层依赖。

build_container() 一次性完成全链装配(Nacos → 配置仓库 → 数据库 → Agent),
产出不可变 Container;资源关闭统一由 AsyncExitStack 逆序执行。
"""
from __future__ import annotations

import logging
import os
from contextlib import AsyncExitStack

from pydantic import BaseModel, ConfigDict, Field

from application.ports.agent_service import AgentService
from domain.shared.ai_tools import AITool
from domain.shared.prompts import DEFAULT_AGENT_PROMPT
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.tool_adapter import adapt_ai_tools
from infrastructure.client.database import DatabaseManager
from infrastructure.client.nacos import NacosClient, NacosConfig
from infrastructure.ports import (
    NacosAgentIdentityRepository,
    NacosSkillConfigRepository,
)
from infrastructure.ports.data_base_config_nacos_repository import (
    NacosPostgresConfigRepository,
)
from infrastructure.ports.nacos_llm_config_repository import NacosLLMConfigRepository
from interfaces.ai.react_agent import LangChainAgentService

logger = logging.getLogger("ai-finance")


class Container(BaseModel):
    """组合根产物:持有全部已装配依赖,构建后不可变。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # 基础设施
    nacos_client: NacosClient
    postgres_config_repo: NacosPostgresConfigRepository
    db_manager: DatabaseManager

    # 配置仓库(已预热)
    agent_identity_repo: NacosAgentIdentityRepository
    skill_config_repo: NacosSkillConfigRepository
    llm_config_repo: NacosLLMConfigRepository

    # AI(agent_service 标端口类型,装饰器替换零改动)
    llm_factory: LLMClientFactory
    tools: list[AITool]
    agent_service: AgentService

    # 资源关闭栈:装配方注册、shutdown 逆序执行
    exit_stack: AsyncExitStack = Field(repr=False)

    async def shutdown(self) -> None:
        """逆序释放全部资源(先数据库后 Nacos)。"""
        await self.exit_stack.aclose()


async def build_container() -> Container:
    """构建并返回组合根容器(async 全链装配)。

    任一步失败时,AsyncExitStack 逆序回收已启动资源后异常上抛(fail-fast)。
    """
    async with AsyncExitStack() as stack:
        # 1. Nacos 客户端
        nacos_config = NacosConfig(
            address=os.getenv("NACOS_ADDRESS", "127.0.0.1:8848"),
            namespace=os.getenv("NACOS_NAMESPACE", "ai-finance"),
        )
        nacos_client = NacosClient(nacos_config)
        await nacos_client.start()
        stack.push_async_callback(nacos_client.stop)

        # 2. 数据库配置 + 管理器
        postgres_config_repo = NacosPostgresConfigRepository(nacos_client)
        await postgres_config_repo.load()
        db_manager = DatabaseManager(postgres_config_repo)
        await db_manager.initialize()
        stack.push_async_callback(db_manager.dispose)

        # 3. 配置仓库预热
        agent_identity_repo = NacosAgentIdentityRepository(nacos_client)
        await agent_identity_repo.load()
        skill_config_repo = NacosSkillConfigRepository(nacos_client)
        await skill_config_repo.load()
        llm_config_repo = NacosLLMConfigRepository(nacos_client)
        await llm_config_repo.load()

        # 4. AI:LLM → 工具 → ReAct Agent → AgentService
        llm_config = llm_config_repo.get()
        llm_factory = LLMClientFactory(llm_config)
        llm = llm_factory.create_llm()
        tools: list[AITool] = []
        lc_tools = adapt_ai_tools(tools)
        agent = create_react_agent(
            llm=llm,
            tools=lc_tools,
            system_prompt=DEFAULT_AGENT_PROMPT.system_text,
        )
        agent_service = LangChainAgentService(agent)

        # 5. 组装容器,关闭栈所有权移交容器
        container = Container(
            nacos_client=nacos_client,
            postgres_config_repo=postgres_config_repo,
            db_manager=db_manager,
            agent_identity_repo=agent_identity_repo,
            skill_config_repo=skill_config_repo,
            llm_config_repo=llm_config_repo,
            llm_factory=llm_factory,
            tools=tools,
            agent_service=agent_service,
            exit_stack=stack.pop_all(),
        )
        logger.info(
            "组合根装配完成: model=%s, prompt=%s@%s",
            llm_config.model,
            DEFAULT_AGENT_PROMPT.name,
            DEFAULT_AGENT_PROMPT.version,
        )
        return container
