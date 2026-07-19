# Agent SSE 流式输出 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `POST /agent/chat/stream`（SSE 流式）与 `POST /agent/chat`（非流式）两个 HTTP 端点，把已就绪的 `AgentService.stream()/run()` 对外暴露，并把 `agent_service` 单例化以让多轮记忆生效。

**Architecture:** 新增代码只在链路首尾两段——interfaces 层的请求/响应 schema + SSE 编码器 + 路由；bootstrap 层把 `agent_service` 在 `lifespan` 预热为单例存入 `app.state`。中间的 `AgentService.stream()`（`interfaces/ai/react_agent.py`）与 `AgentStreamEvent` DTO 全部复用，不改。

**Tech Stack:** FastAPI 0.139、sse-starlette（新增）、Pydantic v2、httpx（仅测试）、unittest。

**对应设计:** [docs/superpowers/specs/2026-07-19-agent-sse-streaming-design.md](../specs/2026-07-19-agent-sse-streaming-design.md)

**与其它计划的关系:** 本计划是 [意图路由计划](2026-07-19-intent-routing.md) 的前置——路由计划会在本计划建立的 `AgentStreamEvent`、单例 `get_agent_service`、`/agent/chat[/stream]` 端点之上扩展，无需改动 interfaces 层。[对话聚合计划](2026-07-19-conversation-aggregate.md) 会把记忆从 LangGraph 迁入领域层并关闭 `MemorySaver`，届时本计划「单例化以保住 MemorySaver 记忆」的动机被对话子域取代——两者可独立实现，集成顺序见各计划说明。

## Global Constraints

以下为全项目硬约束，每个任务都隐含遵守（取值逐字来自 CLAUDE.md）：

- **Python 3.11，一律 `uv run`**：不要用系统 `python3`（那是 3.9）。
- **Pydantic v2 建模，禁止 `dataclasses.dataclass`**：实体/值对象/DTO/配置一律 Pydantic v2。
- **中文**：对话、代码注释、文档、Git 提交信息一律中文。
- **DDD 依赖方向**：`interfaces → application → domain ← infrastructure`；`domain` 不 import 任何框架。本计划新增代码只落在 `interfaces` 与 `bootstrap`。
- **测试用标准库 `unittest`（零依赖）**：异步用例用 `asyncio.run(...)` 驱动，不引入 pytest / pytest-asyncio。
- **提交信息尾行**（每次 commit 都加）：
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/interfaces/http/__init__.py` | 标记 http 入站适配器子包 | 创建 |
| `src/interfaces/http/schemas.py` | `ChatMessage / ChatRequest / ChatResponse` 请求响应模型与 DTO 转换 | 创建 |
| `src/interfaces/http/sse.py` | `AgentStreamEvent` 流 → sse-starlette 帧字典的编码器 | 创建 |
| `src/interfaces/http/agent_router.py` | `/agent/chat` 与 `/agent/chat/stream` 两个路由 | 创建 |
| `src/bootstrap/dependencies.py` | 新增 `get_agent_service`：从 `app.state` 取单例 | 修改 |
| `src/bootstrap/main.py` | `lifespan` 预热 `agent_service` 单例、`include_router` | 修改 |
| `src/bootstrap/container.py` | 修正 `create_llm` 未被调用的既有缺陷（单例路径首次被激活） | 修改 |
| `tests/test_http_schemas.py` | 测 `ChatRequest.to_agent_request` 等 | 创建 |
| `tests/test_sse_encoder.py` | 测 `to_sse_events` | 创建 |
| `tests/test_agent_router.py` | 集成测：注入 stub `AgentService`，验证两端点 | 创建 |
| `pyproject.toml` | 新增 `sse-starlette` 依赖 | 修改（经 `uv add`） |

---

## Task 1: HTTP 请求/响应 Schema

interfaces 层的请求/响应模型，把 HTTP JSON 翻译成 application 层的 `AgentRequest`，并把 `AgentResponse` 翻译回 HTTP。

**Files:**
- Create: `src/interfaces/http/__init__.py`
- Create: `src/interfaces/http/schemas.py`
- Test: `tests/test_http_schemas.py`

**Interfaces:**
- Consumes: `application.dto.agent_dto.AgentRequest`（字段 `messages: list[dict[str,str]]`、`thread_id: str | None`）。
- Produces:
  - `ChatMessage(role: Literal["user","assistant","system"]="user", content: str)`
  - `ChatRequest(messages: list[ChatMessage]=[], thread_id: str | None=None)`，方法 `to_agent_request() -> AgentRequest`
  - `ChatResponse(reply: str, thread_id: str | None=None, tool_calls_count: int=0)`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_http_schemas.py`：

```python
"""interfaces/http/schemas 测试——请求 DTO 转换与响应模型。"""
from __future__ import annotations

import unittest

from application.dto.agent_dto import AgentRequest
from interfaces.http.schemas import ChatMessage, ChatRequest, ChatResponse


class ChatRequestTest(unittest.TestCase):
    def test_to_agent_request_maps_messages(self) -> None:
        """messages 被转为 [{'role','content'}] 并构成 AgentRequest。"""
        req = ChatRequest(
            messages=[ChatMessage(role="user", content="你好")],
            thread_id="t-1",
        )
        agent_req = req.to_agent_request()
        self.assertIsInstance(agent_req, AgentRequest)
        self.assertEqual(agent_req.thread_id, "t-1")
        self.assertEqual(agent_req.messages, [{"role": "user", "content": "你好"}])

    def test_default_role_is_user(self) -> None:
        """ChatMessage 未给 role 时默认 user。"""
        msg = ChatMessage(content="hi")
        self.assertEqual(msg.role, "user")

    def test_empty_request(self) -> None:
        """空请求转换为空 messages、thread_id 为 None。"""
        agent_req = ChatRequest().to_agent_request()
        self.assertEqual(agent_req.messages, [])
        self.assertIsNone(agent_req.thread_id)


class ChatResponseTest(unittest.TestCase):
    def test_fields(self) -> None:
        resp = ChatResponse(reply="答复", thread_id="t-1", tool_calls_count=2)
        self.assertEqual(resp.reply, "答复")
        self.assertEqual(resp.tool_calls_count, 2)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_http_schemas -v`
Expected: FAIL/ERROR —— `ModuleNotFoundError: No module named 'interfaces.http'`

- [ ] **Step 3: 写最小实现**

创建 `src/interfaces/http/__init__.py`（空文件，仅标记包）：

```python
"""interfaces/http —— FastAPI 入站适配器：路由、请求/响应 schema、SSE 编码。"""
```

创建 `src/interfaces/http/schemas.py`：

```python
"""HTTP 请求/响应模型 —— interfaces 层只做翻译，不含业务逻辑。

把 HTTP JSON 翻译为 application 层 AgentRequest，把 AgentResponse 翻译回 HTTP。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from application.dto.agent_dto import AgentRequest


class ChatMessage(BaseModel):
    """单条对话消息。"""

    role: Literal["user", "assistant", "system"] = "user"
    content: str


class ChatRequest(BaseModel):
    """对话请求体（流式/非流式共用）。"""

    messages: list[ChatMessage] = Field(default_factory=list)
    thread_id: str | None = None

    def to_agent_request(self) -> AgentRequest:
        """翻译为 application 层 AgentRequest。"""
        return AgentRequest(
            messages=[m.model_dump() for m in self.messages],
            thread_id=self.thread_id,
        )


class ChatResponse(BaseModel):
    """非流式对话响应体。"""

    reply: str
    thread_id: str | None = None
    tool_calls_count: int = 0
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_http_schemas -v`
Expected: PASS（4 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/http/__init__.py src/interfaces/http/schemas.py tests/test_http_schemas.py
git commit -m "feat: 新增 interfaces/http 请求响应 schema（ChatRequest/ChatResponse）"
```

---

## Task 2: SSE 编码器

把 `AsyncIterator[AgentStreamEvent]` 编码为 sse-starlette 可消费的帧字典 `{"event": <类型>, "data": <JSON>}`。整个事件序列化为 JSON，规避 SSE「多行 data」陷阱。

**Files:**
- Create: `src/interfaces/http/sse.py`
- Test: `tests/test_sse_encoder.py`

**Interfaces:**
- Consumes: `application.dto.agent_dto.AgentStreamEvent`（字段 `event_type`、`content`、`tool_name`、`timestamp`；方法 `model_dump_json()`）。
- Produces: `async def to_sse_events(events: AsyncIterator[AgentStreamEvent]) -> AsyncIterator[dict]`，每帧 `{"event": ev.event_type, "data": ev.model_dump_json()}`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_sse_encoder.py`：

```python
"""interfaces/http/sse 测试——AgentStreamEvent 流 → SSE 帧字典。"""
from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentStreamEvent
from interfaces.http.sse import to_sse_events


async def _make_stream(events: list[AgentStreamEvent]) -> AsyncIterator[AgentStreamEvent]:
    for ev in events:
        yield ev


async def _collect(events: list[AgentStreamEvent]) -> list[dict]:
    return [frame async for frame in to_sse_events(_make_stream(events))]


class ToSseEventsTest(unittest.TestCase):
    def test_frame_shape(self) -> None:
        """每个事件产出 {'event','data'}，event 取事件类型，data 为合法 JSON。"""
        events = [
            AgentStreamEvent(event_type="token", content="发票"),
            AgentStreamEvent(event_type="done", content=""),
        ]
        frames = asyncio.run(_collect(events))
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[0]["event"], "token")
        parsed = json.loads(frames[0]["data"])
        self.assertEqual(parsed["event_type"], "token")
        self.assertEqual(parsed["content"], "发票")
        self.assertEqual(frames[1]["event"], "done")

    def test_empty_stream(self) -> None:
        """空事件流产出空帧列表。"""
        self.assertEqual(asyncio.run(_collect([])), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_sse_encoder -v`
Expected: FAIL/ERROR —— `ModuleNotFoundError: No module named 'interfaces.http.sse'`

- [ ] **Step 3: 写最小实现**

创建 `src/interfaces/http/sse.py`：

```python
"""SSE 编码器 —— 把领域事件流编码为 sse-starlette 帧字典。

整个 AgentStreamEvent 序列化为 JSON 放入 data，换行天然转义，
规避 SSE「多行 data」陷阱；event 取事件类型，供前端按类型分派。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentStreamEvent


async def to_sse_events(
    events: AsyncIterator[AgentStreamEvent],
) -> AsyncIterator[dict]:
    """把 AgentStreamEvent 流编码为 sse-starlette 可消费的帧字典。"""
    async for ev in events:
        yield {"event": ev.event_type, "data": ev.model_dump_json()}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_sse_encoder -v`
Expected: PASS（2 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/interfaces/http/sse.py tests/test_sse_encoder.py
git commit -m "feat: 新增 SSE 编码器 to_sse_events"
```

---

## Task 3: 单例 DI 与 lifespan 预热

把 `agent_service` 单例化：`lifespan` 预热一次存 `app.state.agent_service`，新增 `get_agent_service` DI 从 `app.state` 取单例。这让 `MemorySaver` 常驻、`thread_id` 多轮记忆跨请求生效。同时修正 `container.py` 中 `create_llm` 未被调用的既有缺陷（单例预热是该 AI 装配路径首次被真正激活）。

**Files:**
- Modify: `src/bootstrap/dependencies.py`（新增 `get_agent_service`）
- Modify: `src/bootstrap/container.py:84`（`create_llm` → `create_llm()`）
- Modify: `src/bootstrap/main.py`（`lifespan` 预热单例）
- Test: `tests/test_agent_service_di.py`（新建）

**Interfaces:**
- Consumes: `bootstrap.container.build_container(config=..., skip_db=True)` 返回的 `Container.agent_service`。
- Produces: `get_agent_service(request: Request) -> AgentService`，返回 `request.app.state.agent_service`；缺失时抛 `HTTPException(503)`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_agent_service_di.py`（用轻量假对象模拟 `request.app.state`，不启动真实应用）：

```python
"""get_agent_service DI 测试——从 app.state 取单例，缺失时 503。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from bootstrap.dependencies import get_agent_service


def _fake_request(agent_service: object | None) -> object:
    """构造一个仅含 app.state.agent_service 的假 Request。"""
    state = SimpleNamespace()
    if agent_service is not None:
        state.agent_service = agent_service
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


class GetAgentServiceTest(unittest.TestCase):
    def test_returns_singleton(self) -> None:
        sentinel = object()
        result = get_agent_service(_fake_request(sentinel))
        self.assertIs(result, sentinel)

    def test_missing_raises_503(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            get_agent_service(_fake_request(None))
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_agent_service_di -v`
Expected: FAIL/ERROR —— `ImportError: cannot import name 'get_agent_service'`

- [ ] **Step 3: 写最小实现**

在 `src/bootstrap/dependencies.py` 末尾追加（文件顶部已 `from fastapi import Depends, Request`，需补 `HTTPException`；`AgentService` 从 application 端口导入）：

```python
from fastapi import Depends, HTTPException, Request  # 修改现有导入行，补 HTTPException

from application.ports.agent_service import AgentService  # 新增导入


def get_agent_service(request: Request) -> AgentService:
    """注入 lifespan 预热的 AgentService 单例。

    单例常驻使 MemorySaver 跨请求存活，thread_id 多轮记忆才能生效。
    """
    agent_service = getattr(request.app.state, "agent_service", None)
    if agent_service is None:
        raise HTTPException(status_code=503, detail="AgentService 尚未就绪")
    return agent_service
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_agent_service_di -v`
Expected: PASS（2 个用例）

- [ ] **Step 5: 修正 container.py 既有缺陷并接线 lifespan 预热**

在 `src/bootstrap/container.py` 修正第 84 行——`create_llm` 是方法，需调用：

```python
    # 1. LLM
    llm_factory = LLMClientFactory(config)
    llm: Any = llm_factory.create_llm()   # 修正：原为 llm_factory.create_llm（未调用）
    container.llm_factory = llm_factory
```

在 `src/bootstrap/main.py` 的 `lifespan` 中，`llm_repo.load()` 之后、`yield` 之前追加单例预热：

```python
    # 预热 AgentService 单例：MemorySaver 常驻，thread_id 记忆跨请求生效
    from bootstrap.container import build_container

    container = await build_container(config=llm_repo.get(), skip_db=True)
    app.state.agent_service = container.agent_service
    logger.info("AgentService 已预热（单例）")
```

- [ ] **Step 6: 全量测试确认无回归**

Run: `uv run python -m unittest discover -s tests`
Expected: OK（原有用例 + 新用例全过）

- [ ] **Step 7: 提交**

```bash
git add src/bootstrap/dependencies.py src/bootstrap/container.py src/bootstrap/main.py tests/test_agent_service_di.py
git commit -m "feat: agent_service 单例化（lifespan 预热 + get_agent_service DI），修正 create_llm 未调用缺陷"
```

---

## Task 4: 路由端点 + 依赖接入 + 集成测试

新增 `sse-starlette` 依赖；新增 `agent_router` 暴露 `POST /agent/chat/stream`（SSE）与 `POST /agent/chat`（非流式）；在 `main.py` 注册路由；用注入 stub `AgentService` 的集成测试验证两端点（不打真实 LLM）。

**Files:**
- Modify: `pyproject.toml`（经 `uv add sse-starlette`）
- Create: `src/interfaces/http/agent_router.py`
- Modify: `src/bootstrap/main.py`（`include_router`）
- Test: `tests/test_agent_router.py`

**Interfaces:**
- Consumes: `get_agent_service`（Task 3）、`ChatRequest/ChatResponse`（Task 1）、`to_sse_events`（Task 2）、`AgentService.run/stream`。
- Produces: `interfaces.http.agent_router.router`（`APIRouter(prefix="/agent")`）。

- [ ] **Step 1: 新增依赖**

Run:
```bash
uv add sse-starlette
```
Expected: `pyproject.toml` 的 `dependencies` 新增 `sse-starlette`，`uv.lock` 更新。若与 `fastapi==0.139` 的 starlette 版本冲突，锁定 sse-starlette 到兼容区间后重试。

- [ ] **Step 2: 写失败测试**

创建 `tests/test_agent_router.py`（用 `httpx.ASGITransport` + `app.dependency_overrides` 注入 stub，不跑 lifespan、不连 Nacos、不打 LLM）：

```python
"""agent_router 集成测试——注入 stub AgentService，验证 /agent/chat[/stream]。"""
from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import AsyncIterator

import httpx

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from bootstrap.dependencies import get_agent_service
from bootstrap.main import app


class _StubAgentService:
    """假 AgentService：stream 产出固定事件序列，run 返回固定响应。"""

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply="你好，我是账票助手", thread_id=request.thread_id, tool_calls_count=1)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="token", content="发")
        yield AgentStreamEvent(event_type="token", content="票")
        yield AgentStreamEvent(event_type="done", content="")


def _client() -> httpx.AsyncClient:
    app.dependency_overrides[get_agent_service] = lambda: _StubAgentService()
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


class AgentRouterTest(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_chat_non_stream(self) -> None:
        async def run() -> None:
            async with _client() as client:
                resp = await client.post("/agent/chat", json={"messages": [{"role": "user", "content": "你好"}]})
                self.assertEqual(resp.status_code, 200)
                body = resp.json()
                self.assertEqual(body["reply"], "你好，我是账票助手")
                self.assertEqual(body["tool_calls_count"], 1)

        asyncio.run(run())

    def test_chat_stream_content_type_and_frames(self) -> None:
        async def run() -> None:
            async with _client() as client:
                async with client.stream(
                    "POST", "/agent/chat/stream",
                    json={"messages": [{"role": "user", "content": "你好"}]},
                ) as resp:
                    self.assertEqual(resp.status_code, 200)
                    self.assertTrue(resp.headers["content-type"].startswith("text/event-stream"))
                    events, datas = [], []
                    async for line in resp.aiter_lines():
                        if line.startswith("event:"):
                            events.append(line.split(":", 1)[1].strip())
                        elif line.startswith("data:"):
                            datas.append(json.loads(line.split(":", 1)[1].strip()))
                    self.assertEqual(events, ["token", "token", "done"])
                    self.assertEqual(datas[0]["content"], "发")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_agent_router -v`
Expected: FAIL/ERROR —— 路由不存在（`/agent/chat` 返回 404，断言失败）

- [ ] **Step 4: 写最小实现**

创建 `src/interfaces/http/agent_router.py`：

```python
"""Agent 对话路由 —— 流式（SSE）与非流式两端点。

接口层只翻译：ChatRequest → AgentRequest → 调 AgentService → 翻译回响应。
不含业务逻辑，路由细节对 AgentService 端口透明。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from application.ports.agent_service import AgentService
from bootstrap.dependencies import get_agent_service
from interfaces.http.schemas import ChatRequest, ChatResponse
from interfaces.http.sse import to_sse_events

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
) -> EventSourceResponse:
    """SSE 流式对话：逐 AgentStreamEvent 推送，ping=15s 保活。"""
    stream = agent.stream(req.to_agent_request())
    return EventSourceResponse(to_sse_events(stream), ping=15)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    agent: AgentService = Depends(get_agent_service),
) -> ChatResponse:
    """非流式对话：返回完整回复。"""
    resp = await agent.run(req.to_agent_request())
    return ChatResponse(
        reply=resp.reply,
        thread_id=resp.thread_id,
        tool_calls_count=resp.tool_calls_count,
    )
```

在 `src/bootstrap/main.py` 注册路由（在 `app = FastAPI(...)` 之后、其它路由附近）：

```python
from interfaces.http.agent_router import router as agent_router

app.include_router(agent_router)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_agent_router -v`
Expected: PASS（2 个用例）

- [ ] **Step 6: 全量测试**

Run: `uv run python -m unittest discover -s tests`
Expected: OK（全绿）

- [ ] **Step 7: 提交**

```bash
git add pyproject.toml uv.lock src/interfaces/http/agent_router.py src/bootstrap/main.py tests/test_agent_router.py
git commit -m "feat: 新增 /agent/chat 与 /agent/chat/stream 端点（SSE 流式对话）"
```

---

## Task 5: 端到端手动验证（真实启动）

集成测试用 stub 绕过了真实 LLM 与 lifespan；本任务用真实启动确认单例预热路径（含 Task 3 的 `create_llm` 修正）真的能跑通。

**Files:** 无（仅运行验证）

- [ ] **Step 1: 准备配置**

确认存在 `config/config.json`（含有效 `api_key`、`model` 如 `deepseek-...`），且本地 Nacos 可达（`NACOS_ADDRESS`、`NACOS_NAMESPACE` 环境变量或用默认 `127.0.0.1:8848` / `ai-finance`）。若无 Nacos/Key，跳过本任务并在交付说明中注明「端到端未验证（缺依赖）」。

- [ ] **Step 2: 启动服务**

Run: `uv run python main.py`
Expected: 日志出现 `AgentService 已预热（单例）`，无异常退出。

- [ ] **Step 3: 打非流式端点**

Run:
```bash
curl -s -X POST http://localhost:8000/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"你好"}]}'
```
Expected: 返回 JSON，含非空 `reply`。

- [ ] **Step 4: 打流式端点**

Run:
```bash
curl -N -X POST http://localhost:8000/agent/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"你好"}]}'
```
Expected: 看到 `event: token` / `data: {...}` 逐帧输出，最后 `event: done`。

- [ ] **Step 5: 验证多轮记忆（单例生效）**

先发一条带 `thread_id` 的消息告知信息，再用同一 `thread_id` 追问，确认第二次能记住上文（证明 `MemorySaver` 单例常驻）。停止服务。

---

## Self-Review（写完计划后自查）

**1. Spec 覆盖**（逐条对照设计 §2 目标）：
- `POST /agent/chat/stream`（SSE 推送 `AgentStreamEvent`）→ Task 4 ✅
- `POST /agent/chat`（复用 `run()`）→ Task 4 ✅
- `agent_service` 单例化（lifespan 预热，记忆跨请求）→ Task 3 ✅
- 稳定 SSE 线上协议（`event/data` 帧、整事件 JSON）→ Task 2 编码器落地协议 §5.1/§5.3 ✅
- 依赖变更 `sse-starlette` → Task 4 Step 1 ✅
- 测试策略（`to_sse_events`、`ChatRequest.to_agent_request`、集成测两端点 + 流内 `error`）→ Task 1/2/4 ✅（流内 error：stub 可加一条 error 事件；已由 §5.4 语义覆盖，集成测断言帧类型即可扩展）
- 心跳 `ping=15` / done 收尾 / 断连取消上游 → sse-starlette `EventSourceResponse(ping=15)` 自带，Task 4 已用 ✅

**2. 占位符扫描**：无 TODO / 「适当处理」/ 无代码的测试步骤；每个代码步骤均给出完整代码。

**3. 类型一致性**：`to_sse_events` 签名（Task 2）与 router 调用（Task 4）一致；`get_agent_service`（Task 3）与 router `Depends`（Task 4）一致；`ChatResponse` 字段（Task 1）与 router 构造（Task 4）一致。

**非目标确认**（不做）：不重构 `astream_events` 映射、不迁移 `LangChainAgentService` 分层位置、不做断点续传、不引入 WebSocket、不加 CORS/鉴权（均记为设计 §12 遗留项）。
