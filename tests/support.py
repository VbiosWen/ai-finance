"""测试共享桩:构造零 IO 的 Container。

Container 字段类型是具体基础设施类(Pydantic isinstance 校验),因此桩必须是
这些类的实例/子类;全部不调用 start()/load()/initialize(),构造函数零 IO。
"""
from __future__ import annotations

from contextlib import AsyncExitStack

from application.dto.agent_dto import AgentRequest, AgentResponse
from bootstrap.container import Container
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.client.database import DatabaseManager
from infrastructure.client.nacos import NacosClient, NacosConfig
from infrastructure.config.llm_config import LLMConfig
from infrastructure.ports import (
    NacosAgentIdentityRepository,
    NacosSkillConfigRepository,
)
from infrastructure.ports.data_base_config_nacos_repository import (
    NacosPostgresConfigRepository,
)
from infrastructure.ports.nacos_llm_config_repository import NacosLLMConfigRepository


class StubAgentService:
    """结构性实现 AgentService 端口的桩。"""

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply="stub")

    async def stream(self, request: AgentRequest):
        yield


class LoadedIdentityRepo(NacosAgentIdentityRepository):
    """预置缓存的 AgentIdentity 仓库桩(不连 Nacos)。"""

    def __init__(self, client: NacosClient) -> None:
        super().__init__(client)
        self._cache["agent-identity"] = AgentIdentity(persona="测试助手", tones="正式")
        self._loaded = True


class LoadedSkillRepo(NacosSkillConfigRepository):
    """预置缓存的 SkillConfig 仓库桩(不连 Nacos)。"""

    def __init__(self, client: NacosClient) -> None:
        super().__init__(client)
        self._cache["skill-configs"] = [
            SkillConfig(name="receiving", description="收票", task_instructions="处理收票")
        ]
        self._loaded = True


def make_stub_container(exit_stack: AsyncExitStack | None = None) -> Container:
    """构造零 IO 的 Container 桩,供 bootstrap 层测试使用。"""
    client = NacosClient(NacosConfig())
    postgres_repo = NacosPostgresConfigRepository(client)
    return Container(
        nacos_client=client,
        postgres_config_repo=postgres_repo,
        db_manager=DatabaseManager(postgres_repo),
        agent_identity_repo=LoadedIdentityRepo(client),
        skill_config_repo=LoadedSkillRepo(client),
        llm_config_repo=NacosLLMConfigRepository(client),
        llm_factory=LLMClientFactory(LLMConfig(api_key="test-key")),
        tools=[],
        agent_service=StubAgentService(),
        exit_stack=exit_stack or AsyncExitStack(),
    )
