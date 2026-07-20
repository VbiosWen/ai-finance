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
from application.services.routing_agent_service import RoutingAgentService
from domain.services.routing_policy import RoutingPolicy
from domain.shared.general_skill import GENERAL_SKILL
from domain.shared.ai_tools import AITool
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.ai.llm_intent_recognizer import LlmIntentRecognizer
from infrastructure.ai.skill_agent_builder import build_agent_registry
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

logger = logging.getLogger("ai-finance")

_DEFAULT_IDENTITY = AgentIdentity(persona="AI 账票助手", tones="专业简洁")


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

        # 4. AI:LLM + 多技能 Agent 注册表 + 意图识别 + 路由裁决 → RoutingAgentService
        llm_config = llm_config_repo.get()
        llm_factory = LLMClientFactory(llm_config)
        tools: list[AITool] = []

        identity = agent_identity_repo.get("agent-identity")
        skills = skill_config_repo.get("skill-configs")

        registry = build_agent_registry(
            identity=identity or _DEFAULT_IDENTITY,
            skills=skills or [],
            general_skill=GENERAL_SKILL,
            llm_factory=llm_factory,
        )
        recognizer = LlmIntentRecognizer(llm_factory.create_llm())
        policy = RoutingPolicy(RoutingConfig())

        # 5. 组装为对外唯一 AgentService 入口
        agent_service = RoutingAgentService(recognizer, policy, registry)

        # 6. 组装容器,关闭栈所有权移交容器
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
            "组合根装配完成: model=%s, routing=%d 技能（含兜底 %s）",
            llm_config.model,
            len(skills or []) + 1,
            GENERAL_SKILL.name,
        )
        return container


# ---------------------------------------------------------------------------
# 对话用例装配工厂
# ---------------------------------------------------------------------------

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from application.conversation.send_message import SendMessageUseCase
from infrastructure.conversation.event_publisher import InMemoryEventPublisher
from infrastructure.conversation.repository import SqlAlchemyConversationRepository


def build_conversation_use_case(
    engine: AsyncEngine,
    agent_service: AgentService,
) -> SendMessageUseCase:
    """装配对话用例:SQLAlchemy 仓储 + 进程内发布器(记忆由 Agent 图 checkpointer 承担)。"""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = SqlAlchemyConversationRepository(session_factory)
    publisher = InMemoryEventPublisher()
    return SendMessageUseCase(repo, agent_service, publisher)
