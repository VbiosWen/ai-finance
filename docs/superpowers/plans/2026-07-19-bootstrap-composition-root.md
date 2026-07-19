# Bootstrap 组合根重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按 [设计文档](../specs/2026-07-19-bootstrap-composition-root-design.md) 重构启动链与 DI——`build_container()` 成为唯一 async 装配出口,lifespan 三行化,路由与 DI 胶水归位 interfaces 层,`Container` 转 Pydantic,移除 `/config/{data_id}`。

**Architecture:** 统一 Container 组合根:`build_container()` 内用 `AsyncExitStack` 全链装配(Nacos → 配置仓库 → DatabaseManager → Agent 单例),产出 frozen Pydantic `Container` 挂 `app.state.container`;interfaces 层 DI provider 签名只标 domain/application 端口类型,函数体经 `app.state` 取字段,不 import bootstrap/infrastructure。

**Tech Stack:** Python 3.11(uv)、FastAPI 0.139、Pydantic v2、标准库 unittest、LangChain 1.3.13。

## Global Constraints

- **一律 `uv run` 执行**,不用系统 `python3`(项目要求 3.11)。
- 测试用标准库 **unittest**(零依赖,不引 pytest)。
- **Pydantic v2 建模,禁止 dataclass**。
- 注释、文档、提交信息**一律中文**;提交信息尾部加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- 依赖方向铁律:`interfaces → application → domain ← infrastructure`;interfaces **不得 import** bootstrap / infrastructure。
- 不新增任何依赖(httpx 已随 fastapi 传递安装,TestClient 可用)。
- ⚠️ **仓库有并行会话在改动**(`src/domain/tools/agent_router_tool.py` 处于暂存区且在变动中)。**严禁 `git add -A` / `git add .`**——每次提交只 `git add` 本任务明确列出的文件;开工前先 `git status --short` 核对,若本计划涉及的文件出现计划外改动,停下来向用户确认。
- 现有路由行为保持不变:`/health`、`/agent/identity`、`/agent/skills` 响应与现状一致;`/config/{data_id}` 移除。

---

### Task 1: `AgentService` 端口加 `@runtime_checkable`

`Container.agent_service` 字段将标注 `AgentService` Protocol 类型;Pydantic `arbitrary_types_allowed` 用 `isinstance` 校验,非 `runtime_checkable` 的 Protocol 会抛 `TypeError`。

**Files:**
- Modify: `src/application/ports/agent_service.py`
- Test: `tests/test_agent_service_port.py`(新建)

**Interfaces:**
- Consumes: 无
- Produces: `AgentService`(runtime_checkable Protocol,`isinstance` 可用)——Task 3 的 `Container.agent_service: AgentService` 字段依赖它

- [ ] **Step 1: 写失败测试**

创建 `tests/test_agent_service_port.py`:

```python
"""AgentService 端口的 runtime_checkable 校验测试。"""
import unittest

from application.dto.agent_dto import AgentRequest, AgentResponse
from application.ports.agent_service import AgentService


class _StubAgentService:
    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply="stub")

    async def stream(self, request: AgentRequest):
        yield


class AgentServicePortTest(unittest.TestCase):
    def test_isinstance_accepts_structural_implementation(self) -> None:
        """runtime_checkable 后,结构性实现应通过 isinstance 检查。"""
        self.assertIsInstance(_StubAgentService(), AgentService)

    def test_isinstance_rejects_non_implementation(self) -> None:
        """未实现 run/stream 的对象不通过 isinstance 检查。"""
        self.assertNotIsInstance(object(), AgentService)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m unittest tests.test_agent_service_port -v`
Expected: ERROR,`TypeError: Instance and class checks can only be used with @runtime_checkable protocols`

- [ ] **Step 3: 最小实现**

修改 `src/application/ports/agent_service.py`(两处):

```python
# 原:
from typing import Any, Protocol
# 改为:
from typing import Any, Protocol, runtime_checkable
```

```python
# 原:
class AgentService(Protocol):
# 改为:
@runtime_checkable
class AgentService(Protocol):
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m unittest tests.test_agent_service_port -v`
Expected: `OK`(2 tests)

- [ ] **Step 5: 回归全量测试**

Run: `uv run python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: 无新增失败(现状基线:若 `test_smoke` 等原有用例因环境缺配置而 skip,属正常)

- [ ] **Step 6: 提交**

```bash
git add src/application/ports/agent_service.py tests/test_agent_service_port.py
git commit -m "feat: AgentService 端口加 runtime_checkable,支持 isinstance 校验

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: interfaces/api 包——DI provider 与路由

新建 interfaces 层的 API 包:DI 胶水 + 三个保留路由。此任务不动 bootstrap,旧应用照常工作,新包先以独立测试验证。

**Files:**
- Create: `src/interfaces/api/__init__.py`
- Create: `src/interfaces/api/dependencies.py`
- Create: `src/interfaces/api/routes/__init__.py`
- Create: `src/interfaces/api/routes/health.py`
- Create: `src/interfaces/api/routes/agent_config.py`
- Test: `tests/test_interfaces_api.py`(新建)

**Interfaces:**
- Consumes: `domain.ports.AgentIdentityRepository.get(key: str) -> AgentIdentity`、`domain.ports.SkillConfigRepository.get(key: str) -> list[SkillConfig]`、`application.ports.AgentService`(Task 1)
- Produces: `interfaces.api.routes.all_routers: list[APIRouter]`(Task 4 的 `create_app` 逐个 include);`interfaces.api.dependencies.get_agent_identity_repo / get_skill_config_repo / get_agent_service`(约定:从 `request.app.state.container.<同名字段>` 取)

- [ ] **Step 1: 写失败测试**

创建 `tests/test_interfaces_api.py`(手搭最小 app,容器用鸭子类型桩——interfaces 只读属性,无 isinstance 约束):

```python
"""interfaces/api 路由与 DI provider 测试——手搭最小 app + 鸭子类型桩容器。"""
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from interfaces.api.routes import all_routers


class _StubIdentityRepo:
    def get(self, key: str) -> AgentIdentity:
        return AgentIdentity(persona="测试助手", tones="正式")


class _StubSkillRepo:
    def get(self, key: str) -> list[SkillConfig]:
        return [
            SkillConfig(name="receiving", description="收票", task_instructions="处理收票")
        ]


def _make_app() -> FastAPI:
    app = FastAPI()
    for router in all_routers:
        app.include_router(router)
    app.state.container = SimpleNamespace(
        agent_identity_repo=_StubIdentityRepo(),
        skill_config_repo=_StubSkillRepo(),
    )
    return app


class InterfacesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(_make_app())

    def test_health(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_agent_identity(self) -> None:
        resp = self.client.get("/agent/identity")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["persona"], "测试助手")

    def test_agent_skills(self) -> None:
        resp = self.client.get("/agent/skills")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["name"], "receiving")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m unittest tests.test_interfaces_api -v`
Expected: ERROR,`ModuleNotFoundError: No module named 'interfaces.api'`

- [ ] **Step 3: 实现 interfaces/api 包**

创建 `src/interfaces/api/__init__.py`:

```python
"""API 入站适配器——FastAPI 路由、请求/响应模型、依赖注入胶水。"""
```

创建 `src/interfaces/api/dependencies.py`:

```python
"""FastAPI 依赖注入 provider——从 app.state.container 取已装配依赖。

签名只标 domain / application 端口类型;函数体经 app.state(无类型)取容器字段,
不产生对 bootstrap / infrastructure 的 import,依赖方向保持 interfaces → application → domain。
"""
from __future__ import annotations

from fastapi import Request

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
    """注入应用级单例 AgentService(SSE / chat 端点使用)。"""
    return request.app.state.container.agent_service
```

创建 `src/interfaces/api/routes/health.py`:

```python
"""健康检查路由。"""
from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
```

创建 `src/interfaces/api/routes/agent_config.py`:

```python
"""Agent 配置只读路由——身份定义与技能列表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from domain.ports.agent_identity_repository import AgentIdentityRepository
from domain.ports.skill_config_repository import SkillConfigRepository
from interfaces.api.dependencies import get_agent_identity_repo, get_skill_config_repo

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/identity")
async def agent_identity(
    repo: AgentIdentityRepository = Depends(get_agent_identity_repo),
) -> dict:
    return repo.get("agent-identity").model_dump()


@router.get("/skills")
async def agent_skills(
    repo: SkillConfigRepository = Depends(get_skill_config_repo),
) -> list[dict]:
    return [s.model_dump() for s in repo.get("skill-configs")]
```

创建 `src/interfaces/api/routes/__init__.py`:

```python
"""路由汇总——create_app 统一 include。"""
from fastapi import APIRouter

from interfaces.api.routes.agent_config import router as agent_config_router
from interfaces.api.routes.health import router as health_router

all_routers: list[APIRouter] = [health_router, agent_config_router]

__all__ = ["all_routers"]
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m unittest tests.test_interfaces_api -v`
Expected: `OK`(3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/api tests/test_interfaces_api.py
git commit -m "feat: 新增 interfaces/api 包——DI provider 与 health/agent 路由归位接口层

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 重写 Container(Pydantic + AsyncExitStack)与 build_container 全链装配

`Container` 转 frozen Pydantic 模型;`build_container()` 吞下现 lifespan 的全部装配,资源关闭统一进 `AsyncExitStack`。旧 `test_smoke.py` 测试的 `skip_ai/skip_db` 开关随之删除,由零 IO 桩构造测试取代。

**注**:旧代码 `container.py:84` 的 `llm = llm_factory.create_llm`(漏了调用括号,传出去的是绑定方法)是潜在 bug,本任务顺带修正为 `create_llm()`。

**Files:**
- Modify: `src/bootstrap/container.py`(整文件重写)
- Create: `tests/support.py`(共享桩,Task 4 复用)
- Create: `tests/test_container.py`
- Delete: `tests/test_smoke.py`(用例对着已删除的 `skip_ai/skip_db`,由 `test_container.py` 取代)

**Interfaces:**
- Consumes: `AgentService`(Task 1,runtime_checkable);`NacosClient(NacosConfig).start()/stop()`、`NacosPostgresConfigRepository(client).load()`、`DatabaseManager(repo).initialize()/dispose()`、`NacosAgentIdentityRepository(client).load()`、`NacosSkillConfigRepository(client).load()`、`NacosLLMConfigRepository(client).load()/get()`、`LLMClientFactory(config).create_llm()`、`adapt_ai_tools(list[AITool])`、`create_react_agent(llm, tools, system_prompt)`、`LangChainAgentService(agent)`
- Produces: `Container`(字段:`nacos_client / postgres_config_repo / db_manager / agent_identity_repo / skill_config_repo / llm_config_repo / llm_factory / tools / agent_service / exit_stack`,方法 `async shutdown()`);`async def build_container() -> Container`(无参);测试侧 `tests.support.make_stub_container(exit_stack=None) -> Container` 与 `StubAgentService`——Task 4 直接使用

- [ ] **Step 1: 写共享桩与失败测试**

创建 `tests/support.py`:

```python
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
```

创建 `tests/test_container.py`:

```python
"""Container 构造、不可变性与关闭语义测试——全部零 IO 桩,不触网络/数据库。"""
import asyncio
import unittest
from contextlib import AsyncExitStack

from pydantic import ValidationError

from bootstrap.container import Container
from tests.support import make_stub_container


class ContainerTest(unittest.TestCase):
    def test_construct_with_stubs(self) -> None:
        """零 IO 桩可构造出合法 Container。"""
        container = make_stub_container()
        self.assertIsInstance(container, Container)
        self.assertEqual(container.tools, [])

    def test_frozen(self) -> None:
        """frozen=True:构造后字段不可赋值。"""
        container = make_stub_container()
        with self.assertRaises(ValidationError):
            container.tools = []

    def test_rejects_non_agent_service(self) -> None:
        """agent_service 字段拒绝未实现端口的对象。"""
        base = make_stub_container()
        kwargs = {name: getattr(base, name) for name in Container.model_fields}
        kwargs["agent_service"] = object()
        with self.assertRaises(ValidationError):
            Container(**kwargs)

    def test_shutdown_closes_exit_stack(self) -> None:
        """shutdown() 触发 exit_stack 中注册的关闭回调。"""
        closed: list[str] = []

        async def scenario() -> None:
            stack = AsyncExitStack()

            async def _close() -> None:
                closed.append("closed")

            stack.push_async_callback(_close)
            container = make_stub_container(exit_stack=stack)
            await container.shutdown()

        asyncio.run(scenario())
        self.assertEqual(closed, ["closed"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m unittest tests.test_container -v`
Expected: ERROR——`ValidationError`/`TypeError`(旧 `Container` 是 dataclass,不接受 `nacos_client` 等关键字参数)

- [ ] **Step 3: 重写 container.py**

`src/bootstrap/container.py` 整文件替换为:

```python
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
```

删除旧测试:

```bash
git rm tests/test_smoke.py
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m unittest tests.test_container -v`
Expected: `OK`(4 tests)

- [ ] **Step 5: 回归全量测试**

Run: `uv run python -m unittest discover -s tests -v 2>&1 | tail -5`
Expected: 无失败(`test_smoke` 已删;`bootstrap/dependencies.py` 的 `get_container` 引用的 `build_container` 签名已变,但该函数无路由调用、无测试覆盖,Task 5 将删除整个文件)

- [ ] **Step 6: 提交**

```bash
git add src/bootstrap/container.py tests/support.py tests/test_container.py
git commit -m "refactor: Container 转 Pydantic + build_container 全链 async 装配(AsyncExitStack 管资源)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(注:`git rm tests/test_smoke.py` 已把删除记入暂存区,随本提交一并生效。)

---

### Task 4: bootstrap/app.py——create_app 工厂与 lifespan

应用工厂:注册 lifespan 与 interfaces 路由。生产路径 lifespan 内 `await build_container()`;测试路径传入预制容器(生命周期由调用方管理,lifespan 不代关)。

**Files:**
- Create: `src/bootstrap/app.py`
- Test: `tests/test_bootstrap_app.py`(新建)

**Interfaces:**
- Consumes: `build_container() -> Container`、`Container.shutdown()`(Task 3);`interfaces.api.routes.all_routers`(Task 2);`tests.support.make_stub_container`(Task 3)
- Produces: `create_app(container: Container | None = None) -> FastAPI`、`configure_logging()`——Task 5 的 `main()` 与 uvicorn factory 模式依赖 `create_app` 可零参调用

- [ ] **Step 1: 写失败测试**

创建 `tests/test_bootstrap_app.py`:

```python
"""create_app 工厂 + lifespan + 路由端到端测试(预制桩容器,零 IO)。"""
import unittest
from contextlib import AsyncExitStack

from fastapi.testclient import TestClient

from bootstrap.app import create_app
from tests.support import make_stub_container


class BootstrapAppTest(unittest.TestCase):
    def test_health_and_agent_routes(self) -> None:
        """三个保留路由行为与重构前一致。"""
        with TestClient(create_app(make_stub_container())) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            self.assertEqual(
                client.get("/agent/identity").json()["persona"], "测试助手"
            )
            skills = client.get("/agent/skills").json()
            self.assertEqual(skills[0]["name"], "receiving")

    def test_config_endpoint_removed(self) -> None:
        """/config/{data_id} 已移除(安全)。"""
        with TestClient(create_app(make_stub_container())) as client:
            self.assertEqual(client.get("/config/llm-config").status_code, 404)

    def test_prebuilt_container_not_shutdown_by_lifespan(self) -> None:
        """预制容器由调用方管理生命周期,lifespan 退出不触发 shutdown。"""
        closed: list[str] = []
        stack = AsyncExitStack()

        async def _close() -> None:
            closed.append("closed")

        stack.push_async_callback(_close)
        with TestClient(create_app(make_stub_container(exit_stack=stack))):
            pass
        self.assertEqual(closed, [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行确认失败**

Run: `uv run python -m unittest tests.test_bootstrap_app -v`
Expected: ERROR,`ModuleNotFoundError: No module named 'bootstrap.app'`

- [ ] **Step 3: 实现 app.py**

创建 `src/bootstrap/app.py`:

```python
"""FastAPI 应用工厂与生命周期。

create_app() 创建应用:注册 lifespan 与 interfaces 层路由。
生产路径(container=None)在 lifespan 内 await build_container() 并负责关闭;
测试路径传入预制 Container,生命周期由调用方管理。
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from bootstrap.container import Container, build_container
from interfaces.api.routes import all_routers

logger = logging.getLogger("ai-finance")


def configure_logging() -> None:
    """幂等的全局日志配置(root 已有 handler 时 basicConfig 不生效)。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app(container: Container | None = None) -> FastAPI:
    """创建 FastAPI 应用。

    Args:
        container: 预制容器(测试用),由调用方负责 shutdown;
                   为 None 时(生产)lifespan 内装配并在关闭时释放。
    """
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owns_container = container is None
        app.state.container = await build_container() if owns_container else container
        logger.info("依赖装配完成,服务就绪")
        try:
            yield
        finally:
            if owns_container:
                await app.state.container.shutdown()

    app = FastAPI(
        title="AI Finance 账票服务",
        version="0.1.0",
        lifespan=lifespan,
    )
    for router in all_routers:
        app.include_router(router)
    return app
```

- [ ] **Step 4: 运行确认通过**

Run: `uv run python -m unittest tests.test_bootstrap_app -v`
Expected: `OK`(3 tests)

- [ ] **Step 5: 提交**

```bash
git add src/bootstrap/app.py tests/test_bootstrap_app.py
git commit -m "feat: 新增 create_app 工厂——lifespan 一次装配 Container,include 接口层路由

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 切换启动链——瘦身 main.py、删除旧 DI、修订 CLAUDE.md

旧启动文件切到新链路;删除 `bootstrap/dependencies.py`;CLAUDE.md 组合根一节与实现对齐。根目录 `main.py` 与 Dockerfile(`CMD ["python", "main.py"]`)不动。

**Files:**
- Modify: `src/bootstrap/main.py`(整文件重写)
- Delete: `src/bootstrap/dependencies.py`
- Modify: `CLAUDE.md`(「组合根 bootstrap」一节)

**Interfaces:**
- Consumes: `create_app`(Task 4,经 uvicorn factory 字符串引用 `"bootstrap.app:create_app"`)
- Produces: `bootstrap.main:main`(pyproject `ai-finance` 脚本入口,签名不变)

- [ ] **Step 1: 重写 bootstrap/main.py**

`src/bootstrap/main.py` 整文件替换为:

```python
"""服务启动入口:以 uvicorn factory 模式运行应用工厂。

应用装配见 bootstrap/app.py(create_app + lifespan),
依赖装配见 bootstrap/container.py(build_container)。
开发热重载:uv run uvicorn bootstrap.app:create_app --factory --reload
"""
from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "bootstrap.app:create_app",
        factory=True,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 删除旧 DI 文件并确认无引用**

```bash
git rm src/bootstrap/dependencies.py
grep -rn "bootstrap.dependencies\|from bootstrap import dependencies" src/ tests/ main.py
```

Expected: grep 无输出(退出码 1)。若有输出,逐处改为 `interfaces.api.dependencies` 对应 provider 后重跑。

- [ ] **Step 3: 修订 CLAUDE.md**

「组合根 bootstrap」一节整体替换为:

```markdown
### 组合根 bootstrap

- `bootstrap/container.py` 的 `build_container()`(async):**单一装配出口**,一次性完成 Nacos → 配置仓库预热 → DatabaseManager → Agent 单例全链装配;资源关闭由 `AsyncExitStack` 逆序执行(`Container.shutdown()`)。`Container` 是 frozen Pydantic 模型,`agent_service` 字段标 application 端口类型。
- `bootstrap/app.py` 的 `create_app(container=None)`:FastAPI 应用工厂;生产路径在 lifespan 内 `await build_container()`(异步装配须与 uvicorn 同一事件循环),测试路径传入预制 Container(由调用方负责 shutdown)。
- `bootstrap/main.py` 的 `main()`:仅以 uvicorn factory 模式运行 `bootstrap.app:create_app`。
- FastAPI 的 DI 胶水(`Depends` provider)位于 `interfaces/api/dependencies.py`:签名只标 domain/application 端口类型,函数体从 `app.state.container` 取字段,interfaces 不 import bootstrap/infrastructure。
- 根目录 `main.py` 是**免配置启动器**,仅把 `src` 加入路径后委托给 `bootstrap.main:main`;正式入口是 `pyproject.toml` 里的 `ai-finance` 脚本。
```

- [ ] **Step 4: 全量测试 + 冒烟**

```bash
uv run python -m unittest discover -s tests -v 2>&1 | tail -5
uv run python -c "from bootstrap.app import create_app; app = create_app(); print(sorted(r.path for r in app.routes))"
```

Expected: 测试全绿;冒烟输出的路由列表含 `/health`、`/agent/identity`、`/agent/skills`,**不含** `/config/{data_id}`(FastAPI 自带 `/docs`、`/openapi.json` 等属正常)。

- [ ] **Step 5: 真实启动验证(有 Nacos 环境时)**

若本机 Nacos(127.0.0.1:8848)与配置可用:`uv run python main.py`,观察日志出现「组合根装配完成」「依赖装配完成,服务就绪」,`curl http://127.0.0.1:8000/health` 返回 `{"status":"ok"}` 后 Ctrl+C(应看到数据库与 Nacos 依序关闭日志)。环境不可用则跳过本步,在提交信息与汇报中注明「真实启动待环境验证」。

- [ ] **Step 6: 提交**

```bash
git add src/bootstrap/main.py CLAUDE.md
git commit -m "refactor: 启动链切换到 create_app 工厂,删除 bootstrap/dependencies.py,修订 CLAUDE.md

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

(注:`git rm src/bootstrap/dependencies.py` 已把删除记入暂存区,随本提交一并生效。)
