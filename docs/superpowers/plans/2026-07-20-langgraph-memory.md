# LangGraph 记忆接管实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 多轮记忆改由 LangGraph checkpointer(AsyncPostgresSaver,`thread_id = conversation_id`)维护;路由进图内(RoutingMiddleware);`Conversation` 聚合退化为纯存储;上下文压缩经 `context_middleware` 插槽扩展。

**Architecture:** 单一 `create_agent` 图 + 中间件管道。`RoutingMiddleware.abefore_agent` 每轮做意图识别+裁决并写入图状态,`awrap_model_call` 按裁决动态换技能 prompt;`SummarizationMiddleware` 等压缩件经装配插槽注入;`SendMessageUseCase` 只喂最新一条消息。规格:`docs/superpowers/specs/2026-07-20-langgraph-memory-design.md`。

**Tech Stack:** Python 3.11 / FastAPI / langchain 1.3.13(`create_agent` + `AgentMiddleware`)/ langgraph checkpointer(新增 `langgraph-checkpoint-postgres`)/ SQLAlchemy 2.0 async / unittest。

## Global Constraints

- 一律 `uv run` 执行;测试命令:`uv run python -m unittest discover -s tests`(改造前 138 个用例全绿)。
- 注释、文档、commit 信息一律中文;commit 末尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- 全项目 Pydantic v2,禁 dataclass。**例外**:LangGraph 状态 schema 必须是 `TypedDict`(框架契约,属「兼容第三方库」例外),即本计划的 `RoutingState(AgentState)`。
- DDD 依赖方向:`interfaces → application → domain ← infrastructure`;domain 不 import 任何框架。middleware 是 LangChain 类型,只能住 `infrastructure/`。
- 已实证的 API 事实(勿凭记忆改写):
  - `from langchain.agents.middleware import AgentMiddleware, SummarizationMiddleware`;`from langchain.agents.middleware.types import AgentState`
  - 钩子:`async def abefore_agent(self, state, runtime) -> dict | None`(每轮一次,返回 dict 合并进图状态);`async def awrap_model_call(self, request, handler)`,`request.override(system_prompt=...)` 换 prompt,`request.state` 读图状态
  - 中间件自定义 `__init__` 需调 `super().__init__()`
  - `astream_events(version="v2")` 中 before_agent 钩子表现为 `on_chain_end`、name=`"<类名>.before_agent"`、`data["output"]` 即钩子返回的 dict;**custom stream writer 事件不会出现在 astream_events 里**(勿走此路)
  - `SummarizationMiddleware(model=..., trigger=("tokens", N), keep=("messages", N))`
  - 测试替身:`GenericFakeChatModel(messages=iter([AIMessage(...)]))` + `MemorySaver`(与 AsyncPostgresSaver 同为 `BaseCheckpointSaver`)
- `RoutingConfig` 默认:`confidence_threshold=0.6`,`fallback_skill_name="general"`。
- `src/infrastructure/ai/skill_agent_factory.py`、`dispatch_tool.py`、`tool_registry` 是工具注册子系统,**不在本计划范围,不得改动**。`agent_factory.py`(`create_react_agent`)保留不动。

## 文件结构总览

| 动作 | 路径 | 职责 |
|---|---|---|
| 新建 | `src/infrastructure/client/checkpointer.py` | DSN 转换 + AsyncPostgresSaver 打开/建表助手 |
| 新建 | `src/infrastructure/ai/middleware/__init__.py`、`routing.py` | RoutingState + RoutingMiddleware(路由进图) |
| 新建 | `src/infrastructure/ai/conversation_agent.py` | `build_conversation_agent()` 单图装配工厂 |
| 移动 | `src/interfaces/ai/react_agent.py` → `src/infrastructure/ai/react_agent.py` | 适配器归位 + routing SSE 帧 + routed_skill 回填 |
| 修改 | `src/domain/conversation/repository.py`、`src/infrastructure/conversation/repository.py` | 新增 `get_head` |
| 修改 | `src/application/conversation/send_message.py` | 只喂最新一条,去窗口 |
| 修改 | `src/interfaces/http/schemas.py` | `/agent/chat` 无状态化 |
| 修改 | `src/infrastructure/config/llm_config.py` | `summarization` 配置节 |
| 修改 | `src/bootstrap/container.py` | 装配切换(checkpointer + 单图) |
| 删除 | `src/application/services/routing_agent_service.py`、`agent_registry.py`、`src/infrastructure/ai/skill_agent_builder.py`、`src/domain/conversation/context_window.py`、`src/interfaces/ai/`(整包) | 退役组件 |

---

### Task 1: 依赖接入与 Postgres checkpointer 助手

**Files:**
- Create: `src/infrastructure/client/checkpointer.py`
- Test: `tests/test_checkpointer_helper.py`
- Modify: `pyproject.toml`(经 `uv add`,不手改)

**Interfaces:**
- Produces: `to_psycopg_dsn(dsn: str) -> str`;`async open_postgres_checkpointer(stack: AsyncExitStack, dsn: str) -> AsyncPostgresSaver`(Task 8 的 container 消费)

- [ ] **Step 1: 安装依赖并验证导入**

```bash
uv add langgraph-checkpoint-postgres
uv run python -c "
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
import inspect
print(inspect.signature(AsyncPostgresSaver.from_conn_string))
print('setup 是协程:', inspect.iscoroutinefunction(AsyncPostgresSaver.setup))
"
```

Expected: 打印 `from_conn_string` 签名(含 `conn_string` 参数)且 `setup 是协程: True`。若 `from_conn_string` 签名与预期不符(不是返回异步上下文管理器的 classmethod),停下查 `help(AsyncPostgresSaver.from_conn_string)` 再继续。

- [ ] **Step 2: 写失败测试**

创建 `tests/test_checkpointer_helper.py`:

```python
"""checkpointer 助手测试——DSN 方言剥离(纯函数,不连库)。"""
from __future__ import annotations

import unittest

from infrastructure.client.checkpointer import to_psycopg_dsn


class ToPsycopgDsnTest(unittest.TestCase):
    def test_strips_asyncpg_driver_suffix(self) -> None:
        self.assertEqual(
            to_psycopg_dsn("postgresql+asyncpg://u:p@127.0.0.1:5432/db"),
            "postgresql://u:p@127.0.0.1:5432/db",
        )

    def test_plain_dsn_unchanged(self) -> None:
        self.assertEqual(
            to_psycopg_dsn("postgresql://u:p@h:5432/db"),
            "postgresql://u:p@h:5432/db",
        )

    def test_no_scheme_unchanged(self) -> None:
        self.assertEqual(to_psycopg_dsn("not-a-dsn"), "not-a-dsn")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_checkpointer_helper -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'infrastructure.client.checkpointer'`)

- [ ] **Step 4: 实现**

创建 `src/infrastructure/client/checkpointer.py`:

```python
"""LangGraph Postgres checkpointer 接入助手。

AsyncPostgresSaver 走 psycopg3 直连(非 SQLAlchemy),与业务表共库不同表;
DSN 需从项目统一的 SQLAlchemy 格式(postgresql+asyncpg://)剥掉方言后缀。
"""
from __future__ import annotations

from contextlib import AsyncExitStack

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def to_psycopg_dsn(dsn: str) -> str:
    """把 SQLAlchemy 方言 DSN(scheme+driver://)转为 psycopg 直连 DSN。"""
    scheme, sep, rest = dsn.partition("://")
    if not sep:
        return dsn
    return scheme.split("+", 1)[0] + "://" + rest


async def open_postgres_checkpointer(
    stack: AsyncExitStack, dsn: str
) -> AsyncPostgresSaver:
    """打开 AsyncPostgresSaver 并建 checkpoint 表。

    生命周期挂入 stack,随 Container.shutdown() 逆序关闭;
    setup() 建表沿用 create_conversation_tables 的 MVP 模式(正式迁移待 Alembic)。
    启动期 Postgres 不可达 → 直接抛错(fail-fast,不静默降级为无记忆)。
    """
    saver = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(to_psycopg_dsn(dsn))
    )
    await saver.setup()
    return saver
```

- [ ] **Step 5: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_checkpointer_helper -v`
Expected: PASS(3 个用例)。注:`open_postgres_checkpointer` 需真库,不在单测覆盖(诚实边界,联调冒烟验证)。

- [ ] **Step 6: 全量回归 + 提交**

```bash
uv run python -m unittest discover -s tests
git add pyproject.toml uv.lock src/infrastructure/client/checkpointer.py tests/test_checkpointer_helper.py
git commit -m "feat: 接入 langgraph-checkpoint-postgres 与 checkpointer 打开助手

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 141 个用例全绿(138+3)。

---

### Task 2: 仓储 get_head(只取对话头)

**Files:**
- Modify: `src/domain/conversation/repository.py`
- Modify: `src/infrastructure/conversation/repository.py`
- Test: `tests/test_conversation_repository.py`

**Interfaces:**
- Produces: `ConversationRepository.get_head(cid: ConversationId) -> Conversation | None`(Task 6 的用例消费)。语义:只加载对话头(id/agent/status/时间戳),`messages` 为空——聚合不变量不依赖历史,追加照常。

- [ ] **Step 1: 写失败测试**

在 `tests/test_conversation_repository.py` 的 `ConversationRepositoryTest` 类内追加两个方法(沿用文件里现成的 `_make_repo`/`_agent` 助手):

```python
    def test_get_head_loads_status_without_messages(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            convo = Conversation.start(_agent())
            convo.post_user_message("第一句")
            convo.record_assistant_message("第一答")
            await repo.save(convo)

            head = await repo.get_head(ConversationId(value=convo.id.value))
            self.assertEqual(head.id.value, convo.id.value)
            self.assertEqual(head.status, convo.status)
            self.assertEqual(head.messages, ())  # 头加载不带历史

        asyncio.run(run())

    def test_get_head_missing_returns_none(self) -> None:
        async def run() -> None:
            repo, _ = await _make_repo()
            self.assertIsNone(await repo.get_head(ConversationId(value="f" * 32)))

        asyncio.run(run())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_repository -v`
Expected: 新增两例 ERROR(`AttributeError: ... 'get_head'`),原有用例 PASS。

- [ ] **Step 3: 实现**

`src/domain/conversation/repository.py` 在 `get` 之后追加抽象方法:

```python
    @abstractmethod
    async def get_head(self, cid: ConversationId) -> Conversation | None:
        """只加载对话头(存在性/状态把门用),不载任何历史消息。"""
        ...
```

`src/infrastructure/conversation/repository.py` 在 `get` 方法之后追加实现:

```python
    async def get_head(self, cid: ConversationId) -> Conversation | None:
        async with self._session_factory() as session:
            head = await session.get(ConversationRow, cid.value)
            if head is None:
                return None
            return _to_conversation(head, [])
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_repository -v`
Expected: PASS(7 个用例)。

- [ ] **Step 5: 全量回归 + 提交**

```bash
uv run python -m unittest discover -s tests
git add src/domain/conversation/repository.py src/infrastructure/conversation/repository.py tests/test_conversation_repository.py
git commit -m "feat: 对话仓储新增 get_head——发送链路只做状态把门,不再载历史

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 全绿(143)。

---

### Task 3: RoutingState + RoutingMiddleware(路由进图)

**Files:**
- Create: `src/infrastructure/ai/middleware/__init__.py`
- Create: `src/infrastructure/ai/middleware/routing.py`
- Test: `tests/test_routing_middleware.py`

**Interfaces:**
- Consumes: `IntentRecognizer.recognize(messages: list[dict[str,str]], skills: list[SkillConfig]) -> IntentClassification`(application 端口);`RoutingPolicy.decide(cls, available: set[str]) -> RoutingDecision`、`RoutingPolicy.fallback_name`(domain);`AgentPromptConfig(agent_identity=..., skill=[s]).render() -> str`(domain)
- Produces: `RoutingState`(AgentState 扩展:`routed_skill`/`routing_confidence`/`routing_fallback`);`RoutingMiddleware(recognizer=, policy=, identity=, skills=, general_skill=, recognizer_window=8)`,含 `prompt_for(skill_name: str | None) -> str`(Task 4 装配、Task 5 事件映射按类名 `RoutingMiddleware.before_agent` 消费)

- [ ] **Step 1: 写失败测试**

创建 `tests/test_routing_middleware.py`:

```python
"""RoutingMiddleware 测试——决策写 state、异常/低置信兜底、prompt 选择、窗口裁剪。"""
from __future__ import annotations

import asyncio
import unittest

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.middleware.routing import RoutingMiddleware, _to_dict_messages

RECEIVING = SkillConfig(name="receiving", description="收票", task_instructions="处理收票任务")
GENERAL = SkillConfig(name="general", description="通用", task_instructions="通用应答")
IDENTITY = AgentIdentity(persona="AI 账票助手", tones="专业简洁")


class _StubRecognizer:
    """可注入结果或异常的识别器桩;记录收到的消息以断言窗口裁剪。"""

    def __init__(self, result=None, error=None) -> None:
        self.result, self.error = result, error
        self.seen: list[dict[str, str]] | None = None

    async def recognize(self, messages, skills):
        self.seen = messages
        if self.error:
            raise self.error
        return self.result


def _middleware(recognizer, window: int = 8) -> RoutingMiddleware:
    return RoutingMiddleware(
        recognizer=recognizer,
        policy=RoutingPolicy(RoutingConfig()),
        identity=IDENTITY,
        skills=[RECEIVING],
        general_skill=GENERAL,
        recognizer_window=window,
    )


class BeforeAgentTest(unittest.TestCase):
    def test_writes_decision_into_state(self) -> None:
        stub = _StubRecognizer(IntentClassification(target_skill="receiving", confidence=0.9))
        update = asyncio.run(_middleware(stub).abefore_agent(
            {"messages": [HumanMessage(content="录一张发票")]}, None
        ))
        self.assertEqual(update["routed_skill"], "receiving")
        self.assertFalse(update["routing_fallback"])
        self.assertAlmostEqual(update["routing_confidence"], 0.9)

    def test_recognizer_error_falls_back(self) -> None:
        stub = _StubRecognizer(error=RuntimeError("llm down"))
        update = asyncio.run(_middleware(stub).abefore_agent(
            {"messages": [HumanMessage(content="继续")]}, None
        ))
        self.assertEqual(update["routed_skill"], "general")
        self.assertTrue(update["routing_fallback"])

    def test_low_confidence_falls_back(self) -> None:
        # RoutingConfig 默认阈值 0.6,置信 0.3 → 兜底
        stub = _StubRecognizer(IntentClassification(target_skill="receiving", confidence=0.3))
        update = asyncio.run(_middleware(stub).abefore_agent(
            {"messages": [HumanMessage(content="嗯")]}, None
        ))
        self.assertEqual(update["routed_skill"], "general")
        self.assertTrue(update["routing_fallback"])

    def test_recognizer_sees_tail_window_as_dicts(self) -> None:
        stub = _StubRecognizer(IntentClassification(target_skill=None, confidence=0.0))
        msgs = [SystemMessage(content="系统提示")]
        for i in range(6):
            msgs.append(HumanMessage(content=f"问{i}"))
            msgs.append(AIMessage(content=f"答{i}"))
        asyncio.run(_middleware(stub, window=4).abefore_agent({"messages": msgs}, None))
        self.assertEqual(len(stub.seen), 4)  # 只取尾部 4 条
        self.assertEqual(stub.seen[-1], {"role": "assistant", "content": "答5"})
        self.assertTrue(all(m["role"] in ("user", "assistant") for m in stub.seen))


class MessageConversionTest(unittest.TestCase):
    def test_system_and_empty_skipped(self) -> None:
        msgs = [SystemMessage(content="s"), HumanMessage(content=""), HumanMessage(content="q")]
        self.assertEqual(_to_dict_messages(msgs, 8), [{"role": "user", "content": "q"}])


class PromptSelectionTest(unittest.TestCase):
    def test_prompt_for_skill_and_fallbacks(self) -> None:
        mw = _middleware(_StubRecognizer())
        self.assertIn("处理收票任务", mw.prompt_for("receiving"))
        self.assertIn("通用应答", mw.prompt_for(None))       # 未裁决 → 兜底
        self.assertIn("通用应答", mw.prompt_for("unknown"))  # 未知技能 → 兜底


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_routing_middleware -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'infrastructure.ai.middleware'`)

- [ ] **Step 3: 实现**

创建 `src/infrastructure/ai/middleware/__init__.py`:

```python
"""Agent 图中间件——路由与上下文工程扩展点的家。

新增上下文工程策略(压缩/规划)= 实现 langchain 的 AgentMiddleware 放本包,
经 build_conversation_agent(context_middleware=[...]) 插槽注入。
"""
from infrastructure.ai.middleware.routing import RoutingMiddleware, RoutingState

__all__ = ["RoutingMiddleware", "RoutingState"]
```

创建 `src/infrastructure/ai/middleware/routing.py`:

```python
"""路由中间件——意图识别与技能裁决进图,决策随 checkpoint 留痕。

RoutingState 是 LangGraph 状态 schema,框架契约要求 TypedDict
(项目「兼容第三方库」例外);业务值对象仍一律 Pydantic。
"""
from __future__ import annotations

import logging

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain_core.messages import AIMessage, HumanMessage
from typing_extensions import NotRequired

from application.ports.intent_recognizer import IntentRecognizer
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.agent_prompt_config import AgentPromptConfig
from domain.value_objects.skill_config import SkillConfig

logger = logging.getLogger("ai-finance")


class RoutingState(AgentState):
    """图状态扩展:路由决策通道(随 checkpointer 持久化)。"""

    routed_skill: NotRequired[str]
    routing_confidence: NotRequired[float]
    routing_fallback: NotRequired[bool]


def _to_dict_messages(messages: list, limit: int) -> list[dict[str, str]]:
    """LangChain 消息 → recognizer 的 dict 格式。

    只保留 user/assistant 的非空文本(System/Tool 对意图识别无增益),裁尾部 limit 条。
    """
    dicts: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        else:
            continue
        if isinstance(m.content, str) and m.content:
            dicts.append({"role": role, "content": m.content})
    return dicts[-limit:]


class RoutingMiddleware(AgentMiddleware):
    """每轮识别意图并裁决技能;每次模型调用按裁决动态换技能 prompt。"""

    state_schema = RoutingState

    def __init__(
        self,
        *,
        recognizer: IntentRecognizer,
        policy: RoutingPolicy,
        identity: AgentIdentity,
        skills: list[SkillConfig],
        general_skill: SkillConfig,
        recognizer_window: int = 8,
    ) -> None:
        super().__init__()
        self._recognizer = recognizer
        self._policy = policy
        self._window = recognizer_window
        catalog = [*skills, general_skill]
        self._catalog = catalog
        self._available = {s.name for s in catalog}
        # 技能 prompt 启动期一次渲染(AgentPromptConfig 不可变)
        self._prompts = {
            s.name: AgentPromptConfig(agent_identity=identity, skill=[s]).render()
            for s in catalog
        }

    # ── 每轮一次:意图识别 + 裁决(checkpointer 已回放全史) ──────────
    async def abefore_agent(self, state, runtime):
        history = _to_dict_messages(state["messages"], self._window)
        try:
            cls = await self._recognizer.recognize(history, self._catalog)
        except Exception as exc:  # 识别失败 → 安全降级,绝不让路由搞垮对话
            logger.warning("意图识别失败,降级兜底: %s", exc)
            return {
                "routed_skill": self._policy.fallback_name,
                "routing_confidence": 0.0,
                "routing_fallback": True,
            }
        dec = self._policy.decide(cls, self._available)
        logger.info(
            "路由裁决: target=%s confidence=%.2f → skill=%s fallback=%s reason=%s",
            cls.target_skill, cls.confidence, dec.skill_name, dec.is_fallback, cls.reason,
        )
        return {
            "routed_skill": dec.skill_name,
            "routing_confidence": cls.confidence,
            "routing_fallback": dec.is_fallback,
        }

    # ── 每次模型调用:按裁决换技能 prompt ────────────────────────────
    def prompt_for(self, skill_name: str | None) -> str:
        """按技能名取渲染好的 system prompt;未裁决/未知技能 → 兜底技能。"""
        fallback = self._policy.fallback_name
        return self._prompts.get(skill_name or fallback, self._prompts[fallback])

    async def awrap_model_call(self, request, handler):
        request = request.override(
            system_prompt=self.prompt_for(request.state.get("routed_skill"))
        )
        return await handler(request)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_routing_middleware -v`
Expected: PASS(7 个用例)。

- [ ] **Step 5: 全量回归 + 提交**

```bash
uv run python -m unittest discover -s tests
git add src/infrastructure/ai/middleware/ tests/test_routing_middleware.py
git commit -m "feat: RoutingMiddleware——意图路由进图,决策写入图状态随 checkpoint 留痕

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 全绿(150)。

---

### Task 4: build_conversation_agent 单图装配 + 图级记忆集成测试

**Files:**
- Create: `src/infrastructure/ai/conversation_agent.py`
- Test: `tests/test_conversation_agent.py`

**Interfaces:**
- Consumes: Task 3 的 `RoutingMiddleware(recognizer=, policy=, identity=, skills=, general_skill=)` 与 `prompt_for(None)`
- Produces: `build_conversation_agent(*, llm, identity, skills, general_skill, recognizer, policy, checkpointer=None, context_middleware=()) -> 编译图`(可 `.ainvoke()`/`.astream_events()`;Task 5 集成测试、Task 8 container 消费)

- [ ] **Step 1: 写失败测试**

创建 `tests/test_conversation_agent.py`:

```python
"""图级集成——checkpointer 双轮记忆、动态技能 prompt、context_middleware 插槽顺位。"""
from __future__ import annotations

import asyncio
import unittest

from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.conversation_agent import build_conversation_agent

RECEIVING = SkillConfig(name="receiving", description="收票", task_instructions="处理收票任务")
GENERAL = SkillConfig(name="general", description="通用", task_instructions="通用应答")
IDENTITY = AgentIdentity(persona="AI 账票助手", tones="专业简洁")


class _StubRecognizer:
    async def recognize(self, messages, skills):
        return IntentClassification(target_skill="receiving", confidence=0.9)


class _CaptureMiddleware(AgentMiddleware):
    """插槽探针:记录模型调用现场,并证明自身在路由之后执行。"""

    def __init__(self) -> None:
        super().__init__()
        self.model_calls: list[tuple[str, int, str | None]] = []
        self.before_agent_saw_skill: list[str | None] = []

    async def abefore_agent(self, state, runtime):
        self.before_agent_saw_skill.append(state.get("routed_skill"))
        return None

    async def awrap_model_call(self, request, handler):
        self.model_calls.append(
            (request.system_prompt, len(request.messages),
             request.state.get("routed_skill"))
        )
        return await handler(request)


def _build(capture: _CaptureMiddleware, checkpointer) -> object:
    model = GenericFakeChatModel(
        messages=iter([AIMessage(content="答一"), AIMessage(content="答二")])
    )
    return build_conversation_agent(
        llm=model,
        identity=IDENTITY,
        skills=[RECEIVING],
        general_skill=GENERAL,
        recognizer=_StubRecognizer(),
        policy=RoutingPolicy(RoutingConfig()),
        checkpointer=checkpointer,
        context_middleware=[capture],
    )


class ConversationAgentTest(unittest.TestCase):
    def test_two_turn_memory_and_dynamic_prompt(self) -> None:
        async def run() -> None:
            capture = _CaptureMiddleware()
            agent = _build(capture, MemorySaver())
            cfg = {"configurable": {"thread_id": "t-memory"}}

            await agent.ainvoke({"messages": [{"role": "user", "content": "录发票"}]}, cfg)
            r2 = await agent.ainvoke({"messages": [{"role": "user", "content": "继续"}]}, cfg)

            # 记忆生效:第二轮只喂 1 条,模型却看到 3 条(H,A,H 由 checkpointer 回放)
            self.assertEqual(capture.model_calls[1][1], 3)
            self.assertEqual(len(r2["messages"]), 4)
            # 动态技能 prompt:每次调用都换上 receiving 的渲染 prompt
            self.assertIn("处理收票任务", capture.model_calls[0][0])
            # 插槽顺位:capture 的 before_agent 在路由之后 → 已能看到裁决
            self.assertEqual(capture.before_agent_saw_skill, ["receiving", "receiving"])
            # 决策通道随 checkpoint 持久化
            self.assertEqual(r2.get("routed_skill"), "receiving")

        asyncio.run(run())

    def test_no_checkpointer_is_stateless(self) -> None:
        async def run() -> None:
            capture = _CaptureMiddleware()
            agent = _build(capture, None)
            await agent.ainvoke({"messages": [{"role": "user", "content": "一"}]})
            await agent.ainvoke({"messages": [{"role": "user", "content": "二"}]})
            # 无 checkpointer:两次模型调用各只见 1 条
            self.assertEqual([c[1] for c in capture.model_calls], [1, 1])

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_agent -v`
Expected: FAIL(`ModuleNotFoundError: No module named 'infrastructure.ai.conversation_agent'`)

- [ ] **Step 3: 实现**

创建 `src/infrastructure/ai/conversation_agent.py`:

```python
"""对话 Agent 单图装配——路由/压缩中间件管道 + checkpointer 记忆。"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware

from application.ports.intent_recognizer import IntentRecognizer
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.middleware.routing import RoutingMiddleware

logger = logging.getLogger("ai-finance")


def build_conversation_agent(
    *,
    llm: Any,
    identity: AgentIdentity,
    skills: list[SkillConfig],
    general_skill: SkillConfig,
    recognizer: IntentRecognizer,
    policy: RoutingPolicy,
    checkpointer: Any | None = None,
    context_middleware: Sequence[AgentMiddleware] = (),
) -> Any:
    """装配单一对话 Agent 图。

    中间件顺位固定:RoutingMiddleware 最先(先裁决,后续压缩/执行都可依赖决策);
    context_middleware 是上下文工程插槽(压缩/规划),按传入顺序执行。
    checkpointer=None 时无记忆(测试/一次性调用);多轮记忆按
    config.configurable.thread_id(= conversation_id)组织。
    """
    routing = RoutingMiddleware(
        recognizer=recognizer,
        policy=policy,
        identity=identity,
        skills=skills,
        general_skill=general_skill,
    )
    agent = create_agent(
        model=llm,
        tools=[],
        # 兜底 prompt;实际每次模型调用都被 awrap_model_call 按裁决覆盖
        system_prompt=routing.prompt_for(None),
        middleware=[routing, *context_middleware],
        checkpointer=checkpointer,
    )
    logger.info(
        "对话 Agent 图装配完成:技能 %d(含兜底 %s),上下文中间件 %d,记忆=%s",
        len(skills) + 1,
        general_skill.name,
        len(context_middleware),
        "checkpointer" if checkpointer is not None else "无",
    )
    return agent
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_agent -v`
Expected: PASS(2 个用例)。

- [ ] **Step 5: 全量回归 + 提交**

```bash
uv run python -m unittest discover -s tests
git add src/infrastructure/ai/conversation_agent.py tests/test_conversation_agent.py
git commit -m "feat: build_conversation_agent 单图装配——checkpointer 记忆 + 中间件插槽实证

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 全绿(152)。

---

### Task 5: LangChainAgentService 归位 infrastructure + routing SSE 帧 + routed_skill 回填

**Files:**
- Move: `src/interfaces/ai/react_agent.py` → `src/infrastructure/ai/react_agent.py`
- Delete: `src/interfaces/ai/__init__.py`、`src/interfaces/ai/agent/__init__.py`(整包,搬走后为空壳)
- Modify: `src/infrastructure/ai/skill_agent_builder.py:14`(import 路径,该文件 Task 8 才删,先保活)
- Test: `tests/test_agent_service.py`

**Interfaces:**
- Consumes: Task 4 的 `build_conversation_agent`(集成测试);Task 3 的类名契约 `"RoutingMiddleware.before_agent"`
- Produces: `infrastructure.ai.react_agent.LangChainAgentService`(Task 8 container 消费);`run()` 回填 `AgentResponse.routed_skill`;`stream()` 产出 `routing` SSE 帧(帧格式不变,前端无感)

- [ ] **Step 1: 移动文件并修 import**

```bash
git mv src/interfaces/ai/react_agent.py src/infrastructure/ai/react_agent.py
git rm src/interfaces/ai/__init__.py src/interfaces/ai/agent/__init__.py
```

改 `src/infrastructure/ai/skill_agent_builder.py` 第 13-14 行:

```python
from infrastructure.ai.react_agent import LangChainAgentService
```

(同时删掉上一行「误置于 interfaces/ai」的注释——遗留债已还。)

改 `tests/test_agent_service.py` 第 9 行 import 来源:

```python
from infrastructure.ai.react_agent import (
```

改 `src/infrastructure/ai/react_agent.py` 模块 docstring 首段为:

```python
"""LangChain Agent 适配器——实现 AgentService 端口(基础设施层出站适配器)。
```

- [ ] **Step 2: 跑全量确认迁移无破坏**

Run: `uv run python -m unittest discover -s tests`
Expected: 全绿(152,纯移动不改行为)。

- [ ] **Step 3: 写失败测试(routing 帧映射 + routed_skill 回填)**

在 `tests/test_agent_service.py` 文件顶部 import 区补:

```python
from application.dto.agent_dto import AgentRequest
from infrastructure.ai.react_agent import LangChainAgentService, _map_event
```

文件末尾(`if __name__` 之前)追加:

```python
class RoutingEventMapTest(unittest.TestCase):
    """routing SSE 帧——从 RoutingMiddleware.before_agent 的 on_chain_end 映射。"""

    def test_maps_routing_decision(self) -> None:
        ev = _map_event({
            "event": "on_chain_end",
            "name": "RoutingMiddleware.before_agent",
            "data": {"output": {"routed_skill": "receiving", "routing_fallback": False}},
        })
        self.assertEqual(ev.event_type, "routing")
        self.assertEqual(ev.skill_name, "receiving")
        self.assertEqual(ev.content, "识别意图：receiving")

    def test_fallback_message(self) -> None:
        ev = _map_event({
            "event": "on_chain_end",
            "name": "RoutingMiddleware.before_agent",
            "data": {"output": {"routed_skill": "general", "routing_fallback": True}},
        })
        self.assertEqual(ev.content, "未匹配专业技能，转通用助手")

    def test_other_chain_end_not_routing(self) -> None:
        self.assertIsNone(_map_event({
            "event": "on_chain_end", "name": "model", "data": {"output": {}},
        }))


class RunRoutedSkillTest(unittest.TestCase):
    """run() 从图终态回填 routed_skill(替代已退役的应用层回填)。"""

    def test_run_returns_routed_skill(self) -> None:
        class _FakeGraph:
            async def ainvoke(self, payload, config=None):
                return {"messages": [AIMessage(content="答")], "routed_skill": "receiving"}

        service = LangChainAgentService(_FakeGraph())
        resp = asyncio.run(service.run(AgentRequest(
            messages=[{"role": "user", "content": "hi"}], thread_id="t1",
        )))
        self.assertEqual(resp.reply, "答")
        self.assertEqual(resp.routed_skill, "receiving")
```

同时给该文件 import 区补 `import asyncio`(若已有则跳过)。

- [ ] **Step 4: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_agent_service -v`
Expected: 新增 4 例 FAIL(routing 映射返回 None、`routed_skill` 为 None),旧用例 PASS。

- [ ] **Step 5: 实现**

改 `src/infrastructure/ai/react_agent.py`:

(a) `run()` 中 `return AgentResponse(...)` 改为:

```python
        return AgentResponse(
            reply=reply,
            thread_id=request.thread_id,
            tool_calls_count=tool_call_count,
            routed_skill=result.get("routed_skill"),
        )
```

(b) 模块级工具函数区(`_map_event` 之前)加:

```python
# RoutingMiddleware.before_agent 在事件流中的节点名(类名契约,改类名需同步)
_ROUTING_NODE = "RoutingMiddleware.before_agent"


def _routing_message(skill: str, is_fallback: bool) -> str:
    return "未匹配专业技能，转通用助手" if is_fallback else f"识别意图：{skill}"
```

(c) `_map_event` 内、`--- 顶层 chain 结束` 块之前插入:

```python
    # --- 路由裁决(图内 before_agent 节点闭合) ---
    if event_name == "on_chain_end" and event.get("name") == _ROUTING_NODE:
        output = event.get("data", {}).get("output") or {}
        skill = output.get("routed_skill")
        if skill:
            return AgentStreamEvent(
                event_type="routing",
                skill_name=skill,
                content=_routing_message(skill, bool(output.get("routing_fallback"))),
                timestamp=now,
            )
        return None
```

- [ ] **Step 6: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_agent_service -v`
Expected: PASS。

- [ ] **Step 7: 补图级流式端到端测试(routing 帧真实出现)**

在 `tests/test_agent_service.py` 追加(import 区需再补:`from langchain_core.language_models.fake_chat_models import GenericFakeChatModel`、`from langgraph.checkpoint.memory import MemorySaver`、`from domain.services.routing_policy import RoutingPolicy`、`from domain.value_objects.agent_identity import AgentIdentity`、`from domain.value_objects.intent import IntentClassification`、`from domain.value_objects.routing_config import RoutingConfig`、`from domain.value_objects.skill_config import SkillConfig`、`from infrastructure.ai.conversation_agent import build_conversation_agent`):

```python
class StreamRoutingIntegrationTest(unittest.TestCase):
    """真图流式:routing 帧先于 token,done 收尾。"""

    def test_stream_emits_routing_then_done(self) -> None:
        class _StubRecognizer:
            async def recognize(self, messages, skills):
                return IntentClassification(target_skill="receiving", confidence=0.9)

        graph = build_conversation_agent(
            llm=GenericFakeChatModel(messages=iter([AIMessage(content="好的")])),
            identity=AgentIdentity(persona="AI 账票助手", tones="专业简洁"),
            skills=[SkillConfig(name="receiving", description="收票", task_instructions="处理收票任务")],
            general_skill=SkillConfig(name="general", description="通用", task_instructions="通用应答"),
            recognizer=_StubRecognizer(),
            policy=RoutingPolicy(RoutingConfig()),
            checkpointer=MemorySaver(),
        )
        service = LangChainAgentService(graph)

        async def collect() -> list:
            events = []
            async for ev in service.stream(AgentRequest(
                messages=[{"role": "user", "content": "录发票"}], thread_id="t-sse",
            )):
                events.append(ev)
            return events

        events = asyncio.run(collect())
        types = [e.event_type for e in events]
        self.assertIn("routing", types)
        self.assertIn("done", types)
        self.assertLess(types.index("routing"), types.index("done"))
        routing = events[types.index("routing")]
        self.assertEqual(routing.skill_name, "receiving")
```

Run: `uv run python -m unittest tests.test_agent_service -v`
Expected: PASS。

- [ ] **Step 8: 全量回归 + 提交**

```bash
uv run python -m unittest discover -s tests
git add -A src/interfaces/ai src/infrastructure/ai/react_agent.py src/infrastructure/ai/skill_agent_builder.py tests/test_agent_service.py
git commit -m "feat: LangChainAgentService 归位基础设施层,图内路由映射 routing SSE 帧与 routed_skill 回填

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 全绿(157)。

---

### Task 6: SendMessageUseCase 简化(只喂最新一条)+ ContextWindowPolicy 退役

**Files:**
- Modify: `src/application/conversation/send_message.py`(重写)
- Modify: `src/bootstrap/container.py:154-165`(`build_conversation_use_case` 去窗口)
- Modify: `src/application/dto/agent_dto.py:26-29`(thread_id 语义注释)
- Delete: `src/domain/conversation/context_window.py`、`tests/test_context_window.py`
- Test: `tests/test_send_message_use_case.py`(重写)

**Interfaces:**
- Consumes: Task 2 的 `repo.get_head(cid)`
- Produces: `SendMessageUseCase(repo, agent, publisher)`(三参构造,窗口参数消失);`build_conversation_use_case(engine, agent_service)`(`bootstrap/app.py` 调用处本就未传 window_size,签名兼容)

- [ ] **Step 1: 重写用例测试(先改测试)**

`tests/test_send_message_use_case.py` 整文件替换为:

```python
"""SendMessageUseCase 测试——只喂最新一条、thread_id 驱动记忆、事件、领域把门。"""
from __future__ import annotations

import asyncio
import unittest

from application.conversation.commands import SendMessageCommand
from application.conversation.send_message import SendMessageUseCase
from application.dto.agent_dto import AgentRequest, AgentResponse
from domain.conversation.aggregate import Conversation, ConversationClosedError
from domain.conversation.value_objects import ConversationId
from domain.entities.agent_entity import AgentId


class _FakeRepo:
    def __init__(self) -> None:
        self.saved: dict[str, Conversation] = {}

    async def get_head(self, cid: ConversationId) -> Conversation | None:
        return self.saved.get(cid.value)

    async def save(self, convo: Conversation) -> None:
        convo.pull_new_messages()  # 模拟落库消费 pending
        self.saved[convo.id.value] = convo


class _FakeAgent:
    def __init__(self) -> None:
        self.last_request: AgentRequest | None = None

    async def run(self, request: AgentRequest) -> AgentResponse:
        self.last_request = request
        return AgentResponse(reply="这是助手回复")

    async def stream(self, request: AgentRequest):
        yield  # 未用到
        raise NotImplementedError


class _FakePublisher:
    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


class SendMessageUseCaseTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo, self.agent, self.pub = _FakeRepo(), _FakeAgent(), _FakePublisher()
        self.use_case = SendMessageUseCase(self.repo, self.agent, self.pub)

    def test_new_conversation_feeds_latest_only(self) -> None:
        result = asyncio.run(self.use_case.execute(
            SendMessageCommand(content="查发票 12345", agent_id=AgentId(name="default_agent"))
        ))
        self.assertEqual(result.reply, "这是助手回复")
        # 只喂最新一条(记忆由 checkpointer 按 thread_id 回放)
        self.assertEqual(
            self.agent.last_request.messages,
            [{"role": "user", "content": "查发票 12345"}],
        )
        # thread_id = conversation_id,驱动记忆
        self.assertEqual(self.agent.last_request.thread_id, result.conversation_id)
        self.assertIn(result.conversation_id, self.repo.saved)
        self.assertEqual(len(self.pub.events), 2)  # Started + AssistantResponded

    def test_continue_feeds_latest_only(self) -> None:
        first = asyncio.run(self.use_case.execute(
            SendMessageCommand(content="第一句", agent_id=AgentId(name="default_agent"))
        ))
        self.pub.events.clear()
        second = asyncio.run(self.use_case.execute(
            SendMessageCommand(
                content="第二句", agent_id=AgentId(name="default_agent"),
                conversation_id=first.conversation_id,
            )
        ))
        self.assertEqual(second.conversation_id, first.conversation_id)
        # 续聊同样只带最新一条,不再回放「第一句」
        self.assertEqual(
            self.agent.last_request.messages,
            [{"role": "user", "content": "第二句"}],
        )
        self.assertEqual(len(self.pub.events), 1)  # 仅 AssistantResponded

    def test_closed_conversation_rejected_before_agent(self) -> None:
        convo = Conversation.start(AgentId(name="default_agent"))
        convo.close()
        self.repo.saved[convo.id.value] = convo
        with self.assertRaises(ConversationClosedError):
            asyncio.run(self.use_case.execute(SendMessageCommand(
                content="还在吗", agent_id=AgentId(name="default_agent"),
                conversation_id=convo.id.value,
            )))
        self.assertIsNone(self.agent.last_request)  # 领域把门在进图之前


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_send_message_use_case -v`
Expected: FAIL(构造函数还要 4 参、messages 断言不匹配)。

- [ ] **Step 3: 实现**

`src/application/conversation/send_message.py` 整文件替换为:

```python
"""发送消息用例——对话闭环编排。业务规则在 domain,多轮记忆在 LangGraph checkpointer。"""
from __future__ import annotations

from application.conversation.commands import ChatResult, SendMessageCommand
from application.dto.agent_dto import AgentRequest
from application.ports.agent_service import AgentService
from application.ports.event_publisher import DomainEventPublisher
from domain.conversation.aggregate import Conversation
from domain.conversation.repository import ConversationRepository
from domain.conversation.value_objects import ConversationId


class SendMessageUseCase:
    def __init__(
        self,
        repo: ConversationRepository,
        agent: AgentService,
        publisher: DomainEventPublisher,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._publisher = publisher

    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        convo = None
        if cmd.conversation_id:
            convo = await self._repo.get_head(ConversationId(value=cmd.conversation_id))
        if convo is None:
            convo = Conversation.start(cmd.agent_id)

        convo.post_user_message(cmd.content)                       # 领域把门:CLOSED 拒绝
        request = AgentRequest(
            messages=[{"role": "user", "content": cmd.content}],   # 只喂最新一条
            thread_id=convo.id.value,                              # 驱动 checkpointer 记忆
        )
        response = await self._agent.run(request)                  # 图内:回放→路由→压缩→执行
        convo.record_assistant_message(response.reply)

        await self._repo.save(convo)
        for ev in convo.pull_events():
            await self._publisher.publish(ev)
        return ChatResult(conversation_id=convo.id.value, reply=response.reply)
```

`src/bootstrap/container.py` 文件末尾的对话用例装配段替换为(同时删掉 `from domain.conversation.context_window import ContextWindowPolicy` 这行 import):

```python
def build_conversation_use_case(
    engine: AsyncEngine,
    agent_service: AgentService,
) -> SendMessageUseCase:
    """装配对话用例:SQLAlchemy 仓储 + 进程内发布器(记忆由 Agent 图 checkpointer 承担)。"""
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    repo = SqlAlchemyConversationRepository(session_factory)
    publisher = InMemoryEventPublisher()
    return SendMessageUseCase(repo, agent_service, publisher)
```

`src/application/dto/agent_dto.py` 中 `AgentRequest.thread_id` 的 Field 描述改为:

```python
    thread_id: str | None = Field(
        default=None,
        description="对话线程 ID(= conversation_id),驱动 LangGraph checkpointer 多轮记忆;不传则单发无记忆",
    )
```

删除退役文件:

```bash
git rm src/domain/conversation/context_window.py tests/test_context_window.py
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_send_message_use_case tests.test_conversation_assembly -v`
Expected: PASS(assembly 集成测不受影响:仍两轮落 4 条消息)。

- [ ] **Step 5: 全量回归 + 提交**

```bash
uv run python -m unittest discover -s tests
git add -A
git commit -m "feat: SendMessageUseCase 只喂最新一条,thread_id 驱动记忆;ContextWindowPolicy 退役

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 全绿(约 156:+1 用例,-2 窗口用例;以实际输出为准,0 失败)。

---

### Task 7: /agent/chat 无状态化(不透传 thread_id)

**Files:**
- Modify: `src/interfaces/http/schemas.py:27-32`
- Test: `tests/test_http_schemas.py`

**Interfaces:**
- Produces: `ChatRequest.to_agent_request()` 恒定 `thread_id=None`(⚠️ breaking:`/agent/chat[/stream]` 变纯无状态;多轮走 `/conversations/messages`)

- [ ] **Step 1: 改测试**

`tests/test_http_schemas.py` 中 `test_to_agent_request_maps_messages` 整方法替换为:

```python
    def test_to_agent_request_strips_thread_id(self) -> None:
        """/agent/chat 无状态化:客户端 thread_id 不透传进 Agent(防撞他人会话记忆)。"""
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="你好")],
            thread_id="t-1",
        )
        agent_req = req.to_agent_request()
        self.assertIsInstance(agent_req, AgentRequest)
        self.assertIsNone(agent_req.thread_id)
        self.assertEqual(agent_req.messages, [{"role": "user", "content": "你好"}])
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_http_schemas -v`
Expected: 1 例 FAIL(`'t-1' is not None`)。

- [ ] **Step 3: 实现**

`src/interfaces/http/schemas.py` 的 `to_agent_request` 替换为:

```python
    def to_agent_request(self) -> AgentRequest:
        """翻译为 application 层 AgentRequest。

        /agent/chat 为无状态单发端点:客户端 thread_id 不透传进 Agent
        (Agent 图带 checkpointer 后,透传等于允许绕过会话端点续聊任意
        会话的记忆);字段保留仅作请求日志关联。多轮走 /conversations/messages。
        """
        return AgentRequest(
            messages=[m.model_dump() for m in self.messages],
            thread_id=None,
        )
```

- [ ] **Step 4: 跑测试确认通过 + 全量 + 提交**

```bash
uv run python -m unittest tests.test_http_schemas tests.test_agent_router -v
uv run python -m unittest discover -s tests
git add src/interfaces/http/schemas.py tests/test_http_schemas.py
git commit -m "feat!: /agent/chat 无状态化——thread_id 不再透传,防绕过会话端点撞入他人记忆

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

Expected: 全绿。

---

### Task 8: summarization 配置节 + 组合根切换 + 旧组件退役

**Files:**
- Modify: `src/infrastructure/config/llm_config.py`(重写:加 SummarizationConfig,修 anthropic BaseModel 误用)
- Modify: `src/bootstrap/container.py`(装配切换)
- Modify: `src/interfaces/api/dependencies.py:26-30`(docstring)
- Delete: `src/application/services/routing_agent_service.py`、`src/application/services/agent_registry.py`、`src/infrastructure/ai/skill_agent_builder.py`、`tests/test_routing_agent_service.py`、`tests/test_agent_registry.py`、`tests/test_routing_integration.py`、`tests/test_skill_agent_builder.py`
- Test: `tests/test_llm_config.py`(追加)

**Interfaces:**
- Consumes: Task 1 `open_postgres_checkpointer`、Task 4 `build_conversation_agent`、Task 5 `LangChainAgentService`
- Produces: `LLMConfig.summarization: SummarizationConfig(enabled/trigger_tokens/keep_messages)`;`Container.agent_service` 实现换为「单图 + 适配器」,字段类型不变(`AgentService` 端口),`tests/support.py` 的桩无需改动

- [ ] **Step 1: 写失败测试(配置节)**

`tests/test_llm_config.py` 文件末尾(`if __name__` 之前)追加:

```python
class SummarizationConfigTest(unittest.TestCase):
    """llm-config 的 summarization 节——默认值与 YAML 解析。"""

    def test_defaults(self) -> None:
        from infrastructure.config.llm_config import LLMConfig

        cfg = LLMConfig(api_key="k")
        self.assertTrue(cfg.summarization.enabled)
        self.assertEqual(cfg.summarization.trigger_tokens, 4000)
        self.assertEqual(cfg.summarization.keep_messages, 20)

    def test_parse_nested_node(self) -> None:
        from infrastructure.config.llm_config import LLMConfig

        cfg = LLMConfig(**{
            "api_key": "k",
            "summarization": {"enabled": False, "trigger_tokens": 800, "keep_messages": 6},
        })
        self.assertFalse(cfg.summarization.enabled)
        self.assertEqual(cfg.summarization.trigger_tokens, 800)
        self.assertEqual(cfg.summarization.keep_messages, 6)
```

Run: `uv run python -m unittest tests.test_llm_config -v`
Expected: 2 例 FAIL(`AttributeError: summarization`)。

- [ ] **Step 2: 实现配置节**

`src/infrastructure/config/llm_config.py` 整文件替换为(顺手修掉 `from anthropic import BaseModel` 的误用,统一回 pydantic v2):

```python
from logging import getLogger

from pydantic import BaseModel, Field

logger = getLogger("ai-finance")


class SummarizationConfig(BaseModel):
    """轮次压缩(SummarizationMiddleware)配置——Nacos llm-config 的 summarization 节。"""

    enabled: bool = Field(default=True, description="是否启用轮次压缩")
    trigger_tokens: int = Field(default=4000, description="触发压缩的 token 阈值")
    keep_messages: int = Field(default=20, description="压缩后保留的最近消息条数")


class LLMConfig(BaseModel):
    model: str = Field(default="deepseek-v4-pro", description="llm_model")
    api_key: str = Field(description="llm_api_key")
    max_token: str = Field(default="1M", description="llm_max_token")
    max_retries: int = Field(default=5, description="llm_max_retries")
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig, description="轮次压缩配置"
    )
```

Run: `uv run python -m unittest tests.test_llm_config -v`
Expected: PASS。

- [ ] **Step 3: 组合根切换**

`src/bootstrap/container.py`:

(a) import 区:**删**

```python
from application.services.routing_agent_service import RoutingAgentService
from infrastructure.ai.skill_agent_builder import build_agent_registry
```

**加**

```python
from langchain.agents.middleware import SummarizationMiddleware

from infrastructure.ai.conversation_agent import build_conversation_agent
from infrastructure.ai.react_agent import LangChainAgentService
from infrastructure.client.checkpointer import open_postgres_checkpointer
from infrastructure.config.database_config import PostgresConfig
```

(b) `build_container()` 中第 4、5 段(从 `# 4. AI:...` 到 `agent_service = RoutingAgentService(...)`)整段替换为:

```python
        # 4. AI:LLM + 意图识别 + 路由裁决 + Postgres checkpointer → 单图对话 Agent
        llm_config = llm_config_repo.get()
        llm_factory = LLMClientFactory(llm_config)
        tools: list[AITool] = []

        identity = agent_identity_repo.get("agent-identity")
        skills = skill_config_repo.get("skill-configs")

        llm = llm_factory.create_llm()
        recognizer = LlmIntentRecognizer(llm)
        policy = RoutingPolicy(RoutingConfig())

        # 记忆:AsyncPostgresSaver(与业务表同库不同表;启动失败即 fail-fast)
        pg_config = postgres_config_repo.get_config() or PostgresConfig()
        checkpointer = await open_postgres_checkpointer(stack, pg_config.db_dsn)

        # 上下文工程插槽:MVP 挂轮次压缩;自研策略在此追加
        context_middleware: list = []
        if llm_config.summarization.enabled:
            context_middleware.append(SummarizationMiddleware(
                model=llm,
                trigger=("tokens", llm_config.summarization.trigger_tokens),
                keep=("messages", llm_config.summarization.keep_messages),
            ))

        graph = build_conversation_agent(
            llm=llm,
            identity=identity or _DEFAULT_IDENTITY,
            skills=skills or [],
            general_skill=GENERAL_SKILL,
            recognizer=recognizer,
            policy=policy,
            checkpointer=checkpointer,
            context_middleware=context_middleware,
        )

        # 5. 组装为对外唯一 AgentService 入口(适配器包装单图)
        agent_service = LangChainAgentService(graph)
```

(c) 装配完成日志改为:

```python
        logger.info(
            "组合根装配完成: model=%s, 技能=%d（含兜底 %s）, 压缩中间件=%d",
            llm_config.model,
            len(skills or []) + 1,
            GENERAL_SKILL.name,
            len(context_middleware),
        )
```

(d) `src/interfaces/api/dependencies.py` 的 `get_agent_service` docstring 替换为:

```python
    """注入 lifespan 预热的 AgentService 单例。

    单例常驻使 AsyncPostgresSaver 连接池跨请求存活,thread_id 多轮记忆才能生效。
    """
```

- [ ] **Step 4: 删除退役组件**

```bash
git rm src/application/services/routing_agent_service.py \
       src/application/services/agent_registry.py \
       src/infrastructure/ai/skill_agent_builder.py \
       tests/test_routing_agent_service.py \
       tests/test_agent_registry.py \
       tests/test_routing_integration.py \
       tests/test_skill_agent_builder.py
```

- [ ] **Step 5: 全量回归**

Run: `uv run python -m unittest discover -s tests`
Expected: 全绿,0 失败(用例数较 138 净变化以输出为准)。若出现 import 残留报错,按报错文件清掉对已删模块的引用(已知引用面仅上述删除清单,`tests/support.py` 与 `test_container.py` 不引用退役组件,不应报错)。

- [ ] **Step 6: 提交**

```bash
git add -A
git commit -m "feat: 组合根切换单图对话 Agent——AsyncPostgresSaver 记忆 + summarization 配置节;退役 RoutingAgentService/AgentRegistry/skill_agent_builder

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: 文档与图谱收尾

**Files:**
- Modify: `CLAUDE.md`(核心链路、子域表、技术栈、启动依赖)
- 运行 `graphify update .`

- [ ] **Step 1: 更新 CLAUDE.md**

(a) 「项目简介」的已落地子域列表替换为:

```markdown
已落地的子域:
- **Agent 对话**（`conversation/`）:Conversation 聚合根(纯存储:审计留痕+状态机+领域事件)、SQLAlchemy 持久化;多轮记忆由 LangGraph checkpointer（AsyncPostgresSaver, thread_id=conversation_id）维护
- **意图路由**（`infrastructure/ai/middleware/routing.py`）:路由进图——RoutingMiddleware 每轮意图识别+置信度裁决,按裁决动态换技能 prompt
- **上下文工程扩展点**:`build_conversation_agent(context_middleware=[...])` 插槽,内置 SummarizationMiddleware 轮次压缩,自研策略实现 AgentMiddleware 即插即用
- **SSE 流式输出**:`/agent/chat/stream` 逐 token 推送（routing 帧来自图内 before_agent 节点事件）
```

(b) 「核心链路」两段替换为:

```markdown
**Agent 对话链路**（`/agent/chat[/stream]`,无状态单发,thread_id 不透传）:
HTTP → `ChatRequest.to_agent_request()` → `LangChainAgentService` → 单图 Agent:`RoutingMiddleware.abefore_agent` 意图识别+`RoutingPolicy` 裁决写入图状态 → 压缩中间件 → ReAct 循环(`awrap_model_call` 按裁决换技能 prompt) → `AgentResponse`/`AgentStreamEvent`（含 routing 帧）→ HTTP 响应/SSE 帧

**对话持久化链路**（`/conversations/messages`,多轮记忆入口）:
HTTP → `SendMessageBody` → `SendMessageCommand` → `SendMessageUseCase.execute()` → `Conversation.start()/.post_user_message()`（领域把门:CLOSED 拒绝） → `AgentService.run(最新一条, thread_id=conversation_id)` → 图内 checkpointer 回放全史+路由+压缩+执行 → `Conversation.record_assistant_message()` → `ConversationRepository.save()` append-only 落库（审计事实源） → `DomainEventPublisher.publish()` → `ChatResult`

记忆与存储双轨:**工作记忆真相源 = LangGraph checkpoint（Postgres,含工具中间消息与摘要）;业务事实源 = conversation 表（审计口径）**。两者独立提交,无跨表事务。
```

(c) 「业务子域」表中「Agent 路由」行替换为:

```markdown
| Agent 路由（图内） | `domain/services/routing_policy.py`, `domain/value_objects/intent.py`, `infrastructure/ai/middleware/routing.py`, `infrastructure/ai/llm_intent_recognizer.py` | RoutingMiddleware:意图识别 → 置信度裁决 → 动态技能 prompt |
```

(d) 「AI 基础设施」行替换为:

```markdown
| AI 基础设施 | `infrastructure/ai/` | `LLMClientFactory`、`build_conversation_agent`(单图+中间件)、`react_agent`(AgentService 适配器)、`middleware/`(路由+上下文工程)、`tool_adapter` |
```

(e) 「技术栈」表 AI 行之后加一行:

```markdown
| Agent 记忆 | **langgraph-checkpoint-postgres** (AsyncPostgresSaver) | thread_id=conversation_id;与业务表同库不同表,启动时 setup() 建表 |
```

(f) 「启动依赖」表 `llm-config` 行说明改为:

```markdown
| `llm-config` | YAML | LLM `api_key`、`model`、`base_url`;可选 `summarization` 节（`enabled`/`trigger_tokens`/`keep_messages`,轮次压缩热调参） |
```

并在表格下方补一句:

```markdown
PostgreSQL 中除 conversation 业务表外,LangGraph 会在启动时自建 checkpoint 表（`checkpoints` 等,AsyncPostgresSaver.setup()）。
```

- [ ] **Step 2: 刷新图谱 + 最终回归**

```bash
graphify update .
uv run python -m unittest discover -s tests
```

Expected: 全绿。

- [ ] **Step 3: 提交**

```bash
git add CLAUDE.md graphify-out
git commit -m "docs: CLAUDE.md 对齐 LangGraph 记忆接管后的链路与技术栈;graphify 刷新

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 联调冒烟清单(需真实 Nacos + PostgreSQL,不在单测内)

1. `uv run python main.py` 启动成功,日志出现「对话 Agent 图装配完成」与「组合根装配完成」;Postgres 里出现 LangGraph checkpoint 表。
2. `POST /conversations/messages`(不带 conversation_id)→ 返回 `conversation_id` + 回复;用同一 `conversation_id` 发「继续」→ 回复能接住上文(记忆生效)。
3. 重启服务后用同一 `conversation_id` 续聊 → 上下文仍在(Postgres 持久化生效)。
4. `POST /agent/chat/stream` → 首帧 `routing`,随后 `token`,收尾 `done`;`POST /agent/chat` 带 `thread_id` 两次 → 第二次不携带第一次上下文(无状态化生效)。
5. 把 Nacos `llm-config` 的 `summarization.trigger_tokens` 调小(如 200),长对话数轮后观察模型输入被摘要替换(DEBUG 日志或 checkpoint 表)。
