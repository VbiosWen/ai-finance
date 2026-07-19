# Agent 动态路由与意图识别 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让「一条消息进来 → 显式识别意图 → 选中最合适的技能 Agent → 分发处理」端到端跑通（Phase 1）：新增意图识别器、路由裁决领域服务、多技能 Agent 注册表，以及实现现有 `AgentService` 端口的 `RoutingAgentService`，使 interfaces/SSE 层零改动。

**Architecture:** 严格 DDD 落点——决策数据与策略进 `domain`（`IntentClassification`/`RoutingDecision`/`RoutingPolicy`/`RoutingConfig`/`GENERAL_SKILL`），AI 能力做成端口（`IntentRecognizer`）+ 基础设施实现（`LlmIntentRecognizer` 单次结构化调用、`build_agent_registry` 建多技能 Agent）。编排在 `RoutingAgentService`（application，实现 `AgentService` 端口），bootstrap 把 DI 单例从「单个 agent」换成它，SSE/chat 端点一行不改。

**Tech Stack:** Pydantic v2、LangChain `with_structured_output`、LangChain `create_agent`、unittest（异步用 `asyncio.run`）。

**对应设计:** [docs/superpowers/specs/2026-07-19-intent-routing-design.md](../specs/2026-07-19-intent-routing-design.md)

**前置依赖:** 本计划构建在 [Agent SSE 流式输出计划](2026-07-19-agent-sse-streaming.md) 之上——复用其 `AgentStreamEvent`、单例 `get_agent_service`、`/agent/chat[/stream]` 端点。**请先完成 SSE 计划再执行本计划。** 本计划只把 bootstrap 装配的单例从 `LangChainAgentService` 换成 `RoutingAgentService`，interfaces 层不动。

## Global Constraints

以下为全项目硬约束，每个任务都隐含遵守（取值逐字来自 CLAUDE.md）：

- **Python 3.11，一律 `uv run`**：不要用系统 `python3`。
- **Pydantic v2 建模，禁止 `dataclasses.dataclass`**。
- **中文**：对话、注释、文档、Git 提交信息一律中文。
- **DDD 依赖方向**：`interfaces → application → domain ← infrastructure`；`domain` 不 import 任何框架（LangChain/Pydantic 之外的框架），本计划 domain 层三个组件（`RoutingPolicy`/`IntentClassification`/`RoutingDecision`）必须无框架 import（仅 Pydantic 值对象允许）。
- **测试用标准库 `unittest`（零依赖）**，异步用 `asyncio.run(...)`，不引入 pytest。
- **已知遗留（设计 §12/§13）**：`LangChainAgentService` 现误置于 `interfaces/ai/`（本应在 infrastructure）。Task 7 的 `build_agent_registry`（infrastructure）需 import 它，属该遗留债，本计划不修，待其迁至 infrastructure 后自然干净。
- **提交信息尾行**：
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `src/application/dto/agent_dto.py` | `AgentStreamEvent` 加 `routing` 类型与 `skill_name`；`AgentResponse` 加 `routed_skill` | 修改 |
| `src/domain/value_objects/intent.py` | `IntentClassification` / `RoutingDecision` 值对象 | 创建 |
| `src/domain/value_objects/routing_config.py` | `RoutingConfig` 值对象（阈值/兜底名） | 创建 |
| `src/domain/services/__init__.py` | 领域服务子包标记 | 创建 |
| `src/domain/services/routing_policy.py` | `RoutingPolicy` 无状态领域服务（置信度阈值裁决） | 创建 |
| `src/domain/shared/general_skill.py` | `GENERAL_SKILL`（兜底通用 Agent 的 `SkillConfig` 常量） | 创建 |
| `src/application/ports/intent_recognizer.py` | `IntentRecognizer` 端口（Protocol） | 创建 |
| `src/application/services/__init__.py` | 应用服务子包标记 | 创建 |
| `src/application/services/agent_registry.py` | `AgentRegistry`：`skill_name → (SkillConfig, AgentService)` | 创建 |
| `src/application/services/routing_agent_service.py` | `RoutingAgentService`：识别 → 裁决 → 分发，实现 `AgentService` 端口 | 创建 |
| `src/infrastructure/ai/llm_intent_recognizer.py` | `LlmIntentRecognizer`：`with_structured_output` 单次结构化调用 | 创建 |
| `src/infrastructure/ai/skill_agent_builder.py` | `build_agent_registry(...)`：遍历 skills 建 Agent + 兜底 general | 创建 |
| `src/bootstrap/container.py` | 装配 registry/recognizer/policy → `RoutingAgentService` | 修改 |
| `src/interfaces/http/schemas.py` | `ChatResponse` 加 `routed_skill`（非流式也可观测路由） | 修改 |
| `src/interfaces/http/agent_router.py` | 非流式响应回填 `routed_skill` | 修改 |
| `docs/superpowers/specs/2026-07-19-agent-sse-streaming-design.md` | §5.2/§5.3 补 `routing` 事件（协议同步） | 修改 |
| `tests/test_agent_dto_routing.py` `tests/test_intent_value_objects.py` `tests/test_routing_policy.py` `tests/test_agent_registry.py` `tests/test_routing_agent_service.py` `tests/test_llm_intent_recognizer.py` `tests/test_skill_agent_builder.py` `tests/test_routing_integration.py` | 各任务测试 | 创建 |

---

## Task 1: 扩展流式协议 DTO（新增 routing 事件）

给 `AgentStreamEvent` 追加 `routing` 事件类型与可选 `skill_name`，给 `AgentResponse` 追加可选 `routed_skill`。向后兼容——原 5 类事件不受影响。

**Files:**
- Modify: `src/application/dto/agent_dto.py`
- Test: `tests/test_agent_dto_routing.py`

**Interfaces:**
- Produces:
  - `AgentStreamEvent.event_type: Literal["token","tool_start","tool_end","done","error","routing"]`
  - `AgentStreamEvent.skill_name: str | None = None`
  - `AgentResponse.routed_skill: str | None = None`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_agent_dto_routing.py`：

```python
"""Agent DTO 路由扩展测试——routing 事件与 routed_skill 字段。"""
from __future__ import annotations

import json
import unittest

from application.dto.agent_dto import AgentResponse, AgentStreamEvent


class RoutingEventTest(unittest.TestCase):
    def test_routing_event_type_and_skill_name(self) -> None:
        evt = AgentStreamEvent(event_type="routing", content="识别意图：稽核", skill_name="auditing")
        self.assertEqual(evt.event_type, "routing")
        self.assertEqual(evt.skill_name, "auditing")

    def test_routing_event_json_contains_skill_name(self) -> None:
        evt = AgentStreamEvent(event_type="routing", skill_name="general", content="转通用助手")
        parsed = json.loads(evt.model_dump_json())
        self.assertEqual(parsed["skill_name"], "general")

    def test_token_event_skill_name_defaults_none(self) -> None:
        evt = AgentStreamEvent(event_type="token", content="x")
        self.assertIsNone(evt.skill_name)


class RoutedSkillTest(unittest.TestCase):
    def test_response_routed_skill(self) -> None:
        resp = AgentResponse(reply="ok", routed_skill="auditing")
        self.assertEqual(resp.routed_skill, "auditing")

    def test_response_routed_skill_defaults_none(self) -> None:
        self.assertIsNone(AgentResponse(reply="ok").routed_skill)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_agent_dto_routing -v`
Expected: FAIL —— `AgentStreamEvent` 无 `skill_name`（`ValidationError`/`AttributeError`），`routing` 不在 Literal 中。

- [ ] **Step 3: 写最小实现**

在 `src/application/dto/agent_dto.py` 修改 `AgentStreamEvent` 与 `AgentResponse`：

`AgentResponse` 追加字段（放在 `tool_calls_count` 后）：

```python
    routed_skill: str | None = Field(
        default=None, description="本次路由命中的技能名（动态路由时回填，可观测）"
    )
```

`AgentStreamEvent.event_type` 的 `Literal` 追加 `"routing"`，并新增 `skill_name`：

```python
    event_type: Literal[
        "token", "tool_start", "tool_end", "done", "error", "routing"
    ] = Field(description="事件类型")
    content: str = Field(default="", description="事件内容")
    tool_name: str | None = Field(default=None, description="工具名称（tool_start/tool_end 时有效）")
    skill_name: str | None = Field(
        default=None, description="路由命中的技能名（仅 routing 事件有值）"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="事件时间戳（UTC）",
    )
```

同时把类 docstring 的「支持四种事件类型」段落补上 `routing`（对话路由：本轮转接到的技能）。

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_agent_dto_routing -v`
Expected: PASS（5 个用例）

- [ ] **Step 5: 回归 + 提交**

Run: `uv run python -m unittest discover -s tests`（确认原 DTO/SSE 用例不受影响）

```bash
git add src/application/dto/agent_dto.py tests/test_agent_dto_routing.py
git commit -m "feat: AgentStreamEvent 新增 routing 事件与 skill_name，AgentResponse 新增 routed_skill"
```

---

## Task 2: 意图识别与路由的领域值对象

`IntentClassification`（分类结果）、`RoutingDecision`（裁决结果）、`RoutingConfig`（策略参数）。全部 frozen Pydantic，零框架依赖。

**Files:**
- Create: `src/domain/value_objects/intent.py`
- Create: `src/domain/value_objects/routing_config.py`
- Test: `tests/test_intent_value_objects.py`

**Interfaces:**
- Produces:
  - `IntentClassification(target_skill: str | None=None, confidence: float[0..1], reason: str="")` frozen
  - `RoutingDecision(skill_name: str, is_fallback: bool=False)` frozen
  - `RoutingConfig(confidence_threshold: float[0..1]=0.6, fallback_skill_name: str="general")` frozen

- [ ] **Step 1: 写失败测试**

创建 `tests/test_intent_value_objects.py`：

```python
"""意图/路由值对象测试——字段校验与不可变性。"""
from __future__ import annotations

import unittest

from pydantic import ValidationError

from domain.value_objects.intent import IntentClassification, RoutingDecision
from domain.value_objects.routing_config import RoutingConfig


class IntentClassificationTest(unittest.TestCase):
    def test_defaults(self) -> None:
        c = IntentClassification(confidence=0.5)
        self.assertIsNone(c.target_skill)
        self.assertEqual(c.reason, "")

    def test_confidence_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            IntentClassification(confidence=1.5)
        with self.assertRaises(ValidationError):
            IntentClassification(confidence=-0.1)

    def test_frozen(self) -> None:
        c = IntentClassification(confidence=0.5)
        with self.assertRaises(ValidationError):
            c.confidence = 0.9  # type: ignore[misc]


class RoutingDecisionTest(unittest.TestCase):
    def test_fields(self) -> None:
        d = RoutingDecision(skill_name="auditing")
        self.assertEqual(d.skill_name, "auditing")
        self.assertFalse(d.is_fallback)


class RoutingConfigTest(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = RoutingConfig()
        self.assertEqual(cfg.confidence_threshold, 0.6)
        self.assertEqual(cfg.fallback_skill_name, "general")

    def test_threshold_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            RoutingConfig(confidence_threshold=2.0)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_intent_value_objects -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.value_objects.intent'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/value_objects/intent.py`：

```python
"""意图识别与路由裁决的值对象（不可变，零框架依赖）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    """意图分类结果——分类器只出「技能 + 置信度」，不做裁决。"""

    target_skill: str | None = Field(default=None, description="最匹配技能名；None=识别不出/通用")
    confidence: float = Field(ge=0.0, le=1.0, description="置信度")
    reason: str = Field(default="", description="判断理由（可观测/日志）")

    model_config = {"frozen": True}


class RoutingDecision(BaseModel):
    """路由裁决结果——由 RoutingPolicy 产出。"""

    skill_name: str = Field(description="最终路由到的技能名")
    is_fallback: bool = Field(default=False, description="是否走了兜底")

    model_config = {"frozen": True}
```

创建 `src/domain/value_objects/routing_config.py`：

```python
"""路由策略参数（不可变值对象）。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class RoutingConfig(BaseModel):
    """置信度阈值 + 兜底技能名等策略参数。"""

    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    fallback_skill_name: str = Field(default="general")

    model_config = {"frozen": True}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_intent_value_objects -v`
Expected: PASS（6 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/value_objects/intent.py src/domain/value_objects/routing_config.py tests/test_intent_value_objects.py
git commit -m "feat: 新增意图/路由领域值对象 IntentClassification/RoutingDecision/RoutingConfig"
```

---

## Task 3: RoutingPolicy 领域服务

无状态领域服务：把「识别结果」裁决为「路由目标」。纯逻辑、脱离 LLM 可单测——识别与裁决解耦的最大收益。

**Files:**
- Create: `src/domain/services/__init__.py`
- Create: `src/domain/services/routing_policy.py`
- Test: `tests/test_routing_policy.py`

**Interfaces:**
- Consumes: `RoutingConfig`、`IntentClassification`、`RoutingDecision`（Task 2）。
- Produces: `RoutingPolicy(config: RoutingConfig)`；`decide(c: IntentClassification, available: set[str]) -> RoutingDecision`；`property fallback_name -> str`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_routing_policy.py`：

```python
"""RoutingPolicy 领域服务测试——纯函数裁决，无 mock。"""
from __future__ import annotations

import unittest

from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig


class RoutingPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = RoutingPolicy(RoutingConfig(confidence_threshold=0.6, fallback_skill_name="general"))
        self.available = {"auditing", "receiving", "general"}

    def test_high_confidence_hit(self) -> None:
        c = IntentClassification(target_skill="auditing", confidence=0.9)
        d = self.policy.decide(c, self.available)
        self.assertEqual(d.skill_name, "auditing")
        self.assertFalse(d.is_fallback)

    def test_low_confidence_falls_back(self) -> None:
        c = IntentClassification(target_skill="auditing", confidence=0.3)
        d = self.policy.decide(c, self.available)
        self.assertEqual(d.skill_name, "general")
        self.assertTrue(d.is_fallback)

    def test_none_target_falls_back(self) -> None:
        c = IntentClassification(target_skill=None, confidence=0.95)
        d = self.policy.decide(c, self.available)
        self.assertTrue(d.is_fallback)

    def test_target_not_available_falls_back(self) -> None:
        c = IntentClassification(target_skill="unknown_skill", confidence=0.95)
        d = self.policy.decide(c, self.available)
        self.assertEqual(d.skill_name, "general")
        self.assertTrue(d.is_fallback)

    def test_fallback_name_property(self) -> None:
        self.assertEqual(self.policy.fallback_name, "general")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_routing_policy -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.services'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/services/__init__.py`：

```python
"""领域服务 —— 承载跨聚合、无自然归属的领域逻辑（无状态）。"""
```

创建 `src/domain/services/routing_policy.py`：

```python
"""路由裁决领域服务 —— 无状态，脱离 LLM 可单测。"""
from __future__ import annotations

from domain.value_objects.intent import IntentClassification, RoutingDecision
from domain.value_objects.routing_config import RoutingConfig


class RoutingPolicy:
    """把「识别结果」裁决为「路由目标」。"""

    def __init__(self, config: RoutingConfig) -> None:
        self._config = config

    @property
    def fallback_name(self) -> str:
        return self._config.fallback_skill_name

    def decide(self, c: IntentClassification, available: set[str]) -> RoutingDecision:
        """置信度阈值裁决：低置信/无匹配/不在可路由集 → 兜底。"""
        target = c.target_skill
        if (
            target is None
            or target not in available
            or c.confidence < self._config.confidence_threshold
        ):
            return RoutingDecision(skill_name=self._config.fallback_skill_name, is_fallback=True)
        return RoutingDecision(skill_name=target, is_fallback=False)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_routing_policy -v`
Expected: PASS（5 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/services/__init__.py src/domain/services/routing_policy.py tests/test_routing_policy.py
git commit -m "feat: 新增 RoutingPolicy 路由裁决领域服务"
```

---

## Task 4: GENERAL_SKILL + IntentRecognizer 端口 + AgentRegistry

兜底通用技能常量（domain）、意图识别端口（application Protocol）、多技能注册表（application）。注册表构造时 fail-fast 校验兜底技能必须存在。

**Files:**
- Create: `src/domain/shared/general_skill.py`
- Create: `src/application/ports/intent_recognizer.py`
- Create: `src/application/services/__init__.py`
- Create: `src/application/services/agent_registry.py`
- Test: `tests/test_agent_registry.py`

**Interfaces:**
- Consumes: `SkillConfig`（`domain.value_objects.skill_config`）、`AgentService`（`application.ports.agent_service`）、`IntentClassification`（Task 2）。
- Produces:
  - `GENERAL_SKILL: SkillConfig`（`name == "general"`）
  - `IntentRecognizer`（Protocol）：`async recognize(messages: list[dict[str,str]], skills: list[SkillConfig]) -> IntentClassification`
  - `AgentRegistry(entries: dict[str, tuple[SkillConfig, AgentService]], fallback: str)`；方法 `get(skill_name) -> AgentService`、`available() -> set[str]`、`catalog() -> list[SkillConfig]`；无兜底 → 构造抛 `ValueError`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_agent_registry.py`：

```python
"""AgentRegistry 测试——get/available/catalog、缺失兜底、无兜底抛错。"""
from __future__ import annotations

import unittest
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.services.agent_registry import AgentRegistry
from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.skill_config import SkillConfig


class _StubService:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=self.tag)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="done")


def _skill(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=f"{name} 技能", task_instructions="做事")


def _registry() -> AgentRegistry:
    entries = {
        "auditing": (_skill("auditing"), _StubService("auditing")),
        "general": (GENERAL_SKILL, _StubService("general")),
    }
    return AgentRegistry(entries, fallback="general")


class AgentRegistryTest(unittest.TestCase):
    def test_general_skill_name(self) -> None:
        self.assertEqual(GENERAL_SKILL.name, "general")

    def test_get_hit(self) -> None:
        self.assertEqual(_registry().get("auditing").tag, "auditing")

    def test_get_missing_returns_fallback(self) -> None:
        self.assertEqual(_registry().get("不存在").tag, "general")

    def test_available(self) -> None:
        self.assertEqual(_registry().available(), {"auditing", "general"})

    def test_catalog_contains_skill_configs(self) -> None:
        names = {s.name for s in _registry().catalog()}
        self.assertEqual(names, {"auditing", "general"})

    def test_missing_fallback_raises(self) -> None:
        with self.assertRaises(ValueError):
            AgentRegistry({"auditing": (_skill("auditing"), _StubService("a"))}, fallback="general")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_agent_registry -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'domain.shared.general_skill'`

- [ ] **Step 3: 写最小实现**

创建 `src/domain/shared/general_skill.py`：

```python
"""兜底通用技能 —— 接住一切无法归类的请求，保证体验连贯。"""
from __future__ import annotations

from domain.value_objects.skill_config import SkillConfig

GENERAL_SKILL = SkillConfig(
    name="general",
    description="通用助手，处理未匹配到专业技能的账票相关请求以及日常对话。",
    task_instructions=(
        "作为账票领域的通用助手，礼貌地理解用户意图并尽力回答；"
        "遇到明显属于收票或稽核的专业请求时，正常作答即可。"
    ),
    version="1.0.0",
)
```

创建 `src/application/ports/intent_recognizer.py`：

```python
"""意图识别端口 —— 输入对话 + 技能目录，输出结构化分类结果。"""
from __future__ import annotations

from typing import Protocol

from domain.value_objects.intent import IntentClassification
from domain.value_objects.skill_config import SkillConfig


class IntentRecognizer(Protocol):
    async def recognize(
        self,
        messages: list[dict[str, str]],
        skills: list[SkillConfig],
    ) -> IntentClassification:
        """识别当前对话最匹配的技能。基础设施层用 LLM 结构化输出实现。"""
        ...
```

创建 `src/application/services/__init__.py`：

```python
"""应用服务 —— 用例/编排组件（不含业务规则，业务规则在 domain）。"""
```

创建 `src/application/services/agent_registry.py`：

```python
"""多技能 Agent 注册表 —— 分类器目录与可路由集合同源。"""
from __future__ import annotations

from application.ports.agent_service import AgentService
from domain.value_objects.skill_config import SkillConfig


class AgentRegistry:
    """skill_name → (SkillConfig, AgentService)。"""

    def __init__(
        self,
        entries: dict[str, tuple[SkillConfig, AgentService]],
        fallback: str,
    ) -> None:
        if fallback not in entries:  # fail-fast：兜底必须存在
            raise ValueError(f"兜底技能 '{fallback}' 未注册，无法启动")
        self._entries = entries
        self._fallback = fallback

    def get(self, skill_name: str) -> AgentService:
        entry = self._entries.get(skill_name) or self._entries[self._fallback]
        return entry[1]

    def available(self) -> set[str]:
        return set(self._entries.keys())

    def catalog(self) -> list[SkillConfig]:
        return [cfg for cfg, _ in self._entries.values()]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_agent_registry -v`
Expected: PASS（6 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/domain/shared/general_skill.py src/application/ports/intent_recognizer.py src/application/services/__init__.py src/application/services/agent_registry.py tests/test_agent_registry.py
git commit -m "feat: 新增 GENERAL_SKILL、IntentRecognizer 端口与 AgentRegistry"
```

---

## Task 5: RoutingAgentService（编排：识别 → 裁决 → 分发）

实现现有 `AgentService` 端口。`run` 与 `stream` 都先 `_route`（识别 + 裁决，识别失败安全降级兜底），再委托选中的 worker；`stream` 先发一帧 `routing` 事件，`run` 回填 `routed_skill`。

**Files:**
- Create: `src/application/services/routing_agent_service.py`
- Test: `tests/test_routing_agent_service.py`

**Interfaces:**
- Consumes: `IntentRecognizer`（Task 4）、`RoutingPolicy`（Task 3）、`AgentRegistry`（Task 4）、`AgentRequest/Response/StreamEvent`（Task 1）、`RoutingDecision`（Task 2）。
- Produces: `RoutingAgentService(recognizer: IntentRecognizer, policy: RoutingPolicy, registry: AgentRegistry)`，实现 `AgentService` 端口（`run`/`stream`）。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_routing_agent_service.py`：

```python
"""RoutingAgentService 测试——路由分发、routing 首帧、失败降级、run 回填。"""
from __future__ import annotations

import asyncio
import unittest
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.services.agent_registry import AgentRegistry
from application.services.routing_agent_service import RoutingAgentService
from domain.services.routing_policy import RoutingPolicy
from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig


class _StubWorker:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=self.tag)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="token", content=self.tag)
        yield AgentStreamEvent(event_type="done")


class _StubRecognizer:
    def __init__(self, result: IntentClassification | None, *, raise_exc: bool = False) -> None:
        self._result = result
        self._raise = raise_exc

    async def recognize(self, messages, skills) -> IntentClassification:
        if self._raise:
            raise RuntimeError("分类器炸了")
        return self._result


def _skill(name: str) -> SkillConfig:
    return SkillConfig(name=name, description=f"{name} 技能", task_instructions="做事")


def _service(recognizer: _StubRecognizer) -> RoutingAgentService:
    registry = AgentRegistry(
        {
            "auditing": (_skill("auditing"), _StubWorker("auditing")),
            "general": (GENERAL_SKILL, _StubWorker("general")),
        },
        fallback="general",
    )
    policy = RoutingPolicy(RoutingConfig())
    return RoutingAgentService(recognizer, policy, registry)


class RoutingAgentServiceTest(unittest.TestCase):
    def test_routes_to_matched_worker(self) -> None:
        svc = _service(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.9)))
        resp = asyncio.run(svc.run(AgentRequest(messages=[{"role": "user", "content": "帮我稽核"}])))
        self.assertEqual(resp.reply, "auditing")
        self.assertEqual(resp.routed_skill, "auditing")

    def test_stream_emits_routing_first(self) -> None:
        svc = _service(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.9)))

        async def collect() -> list[AgentStreamEvent]:
            return [ev async for ev in svc.stream(AgentRequest(messages=[{"role": "user", "content": "x"}]))]

        events = asyncio.run(collect())
        self.assertEqual(events[0].event_type, "routing")
        self.assertEqual(events[0].skill_name, "auditing")
        self.assertEqual(events[1].event_type, "token")
        self.assertEqual(events[1].content, "auditing")

    def test_low_confidence_falls_back_to_general(self) -> None:
        svc = _service(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.2)))
        resp = asyncio.run(svc.run(AgentRequest(messages=[{"role": "user", "content": "闲聊"}])))
        self.assertEqual(resp.routed_skill, "general")

    def test_recognizer_failure_degrades_to_general(self) -> None:
        svc = _service(_StubRecognizer(None, raise_exc=True))
        resp = asyncio.run(svc.run(AgentRequest(messages=[{"role": "user", "content": "x"}])))
        self.assertEqual(resp.reply, "general")
        self.assertEqual(resp.routed_skill, "general")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_routing_agent_service -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'application.services.routing_agent_service'`

- [ ] **Step 3: 写最小实现**

创建 `src/application/services/routing_agent_service.py`：

```python
"""路由 Agent 服务 —— 实现 AgentService 端口，内敛路由复杂度。

编排：意图识别 → RoutingPolicy 裁决 → 分发到选中的技能/兜底 Agent。
识别任一环节失败都安全降级兜底，绝不让路由失败演变成整通对话失败。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.ports.agent_service import AgentService
from application.ports.intent_recognizer import IntentRecognizer
from application.services.agent_registry import AgentRegistry
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.intent import RoutingDecision

logger = logging.getLogger("ai-finance")


def _routing_message(dec: RoutingDecision) -> str:
    if dec.is_fallback:
        return "未匹配专业技能，转通用助手"
    return f"识别意图：{dec.skill_name}"


class RoutingAgentService:
    """实现 AgentService 端口（run / stream）。"""

    def __init__(
        self,
        recognizer: IntentRecognizer,
        policy: RoutingPolicy,
        registry: AgentRegistry,
    ) -> None:
        self._recognizer = recognizer
        self._policy = policy
        self._registry = registry

    async def _route(self, req: AgentRequest) -> RoutingDecision:
        catalog = self._registry.catalog()
        try:
            cls = await self._recognizer.recognize(req.messages, catalog)
        except Exception as exc:  # 识别失败 → 安全降级
            logger.warning("意图识别失败，降级兜底: %s", exc)
            return RoutingDecision(skill_name=self._policy.fallback_name, is_fallback=True)
        dec = self._policy.decide(cls, self._registry.available())
        logger.info(
            "路由裁决: target=%s confidence=%.2f → skill=%s fallback=%s reason=%s",
            cls.target_skill, cls.confidence, dec.skill_name, dec.is_fallback, cls.reason,
        )
        return dec

    async def run(self, req: AgentRequest) -> AgentResponse:
        dec = await self._route(req)
        resp = await self._registry.get(dec.skill_name).run(req)
        return resp.model_copy(update={"routed_skill": dec.skill_name})

    async def stream(self, req: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        dec = await self._route(req)
        yield AgentStreamEvent(
            event_type="routing",
            skill_name=dec.skill_name,
            content=_routing_message(dec),
        )
        async for ev in self._registry.get(dec.skill_name).stream(req):
            yield ev
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_routing_agent_service -v`
Expected: PASS（4 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/application/services/routing_agent_service.py tests/test_routing_agent_service.py
git commit -m "feat: 新增 RoutingAgentService（识别→裁决→分发，实现 AgentService 端口）"
```

---

## Task 6: LlmIntentRecognizer（基础设施结构化调用）

实现 `IntentRecognizer` 端口：`llm.with_structured_output(IntentClassification)` 单次结构化调用；prompt 由 `SkillConfig.name + description` 拼技能目录。不是 ReAct agent，更快更省。

**Files:**
- Create: `src/infrastructure/ai/llm_intent_recognizer.py`
- Test: `tests/test_llm_intent_recognizer.py`

**Interfaces:**
- Consumes: `IntentClassification`（Task 2）、`SkillConfig`。
- Produces: `LlmIntentRecognizer(llm)`；模块函数 `_build_classify_prompt(catalog: str, messages: list[dict[str,str]]) -> str`；`async recognize(messages, skills) -> IntentClassification`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_llm_intent_recognizer.py`（用假 LLM，不打真实模型）：

```python
"""LlmIntentRecognizer 测试——prompt 拼装 + 结构化输出解析（假 LLM）。"""
from __future__ import annotations

import asyncio
import unittest

from domain.value_objects.intent import IntentClassification
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.llm_intent_recognizer import (
    LlmIntentRecognizer,
    _build_classify_prompt,
)


class _FakeStructured:
    def __init__(self, result: IntentClassification) -> None:
        self._result = result
        self.last_prompt: str | None = None

    async def ainvoke(self, prompt: str) -> IntentClassification:
        self.last_prompt = prompt
        return self._result


class _FakeLLM:
    def __init__(self, result: IntentClassification) -> None:
        self._structured = _FakeStructured(result)

    def with_structured_output(self, schema: type) -> _FakeStructured:
        return self._structured


def _skills() -> list[SkillConfig]:
    return [
        SkillConfig(name="auditing", description="发票稽核与合规校验", task_instructions="稽核"),
        SkillConfig(name="receiving", description="发票收票与信息提取", task_instructions="收票"),
    ]


class BuildPromptTest(unittest.TestCase):
    def test_prompt_contains_each_skill(self) -> None:
        catalog = "\n".join(f"- {s.name}: {s.description}" for s in _skills())
        prompt = _build_classify_prompt(catalog, [{"role": "user", "content": "帮我稽核发票"}])
        self.assertIn("auditing", prompt)
        self.assertIn("发票稽核与合规校验", prompt)
        self.assertIn("receiving", prompt)
        self.assertIn("帮我稽核发票", prompt)


class RecognizeTest(unittest.TestCase):
    def test_recognize_returns_structured_result(self) -> None:
        expected = IntentClassification(target_skill="auditing", confidence=0.88, reason="含稽核意图")
        llm = _FakeLLM(expected)
        rec = LlmIntentRecognizer(llm)
        result = asyncio.run(rec.recognize([{"role": "user", "content": "帮我稽核发票"}], _skills()))
        self.assertEqual(result.target_skill, "auditing")
        self.assertIn("auditing: 发票稽核与合规校验", llm._structured.last_prompt)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_llm_intent_recognizer -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'infrastructure.ai.llm_intent_recognizer'`

- [ ] **Step 3: 写最小实现**

创建 `src/infrastructure/ai/llm_intent_recognizer.py`：

```python
"""基于 LLM 结构化输出的意图识别器 —— 实现 IntentRecognizer 端口。

单次 with_structured_output 调用，不是 ReAct agent，更快更省。
IntentClassification 是纯 Pydantic 值对象，其 schema 在基础设施层被读取，
领域层保持洁净。
"""
from __future__ import annotations

import logging
from typing import Any

from domain.value_objects.intent import IntentClassification
from domain.value_objects.skill_config import SkillConfig

logger = logging.getLogger("ai-finance")


def _build_classify_prompt(catalog: str, messages: list[dict[str, str]]) -> str:
    """拼装分类 prompt：列技能目录 + 要求择一 + 允许 None。"""
    conversation = "\n".join(f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages)
    return (
        "你是账票服务的意图识别器。下面是可用技能目录（名称: 简介）：\n"
        f"{catalog}\n\n"
        "根据以下对话，判断用户最匹配哪一个技能。\n"
        f"对话：\n{conversation}\n\n"
        "只输出结构化结果：最匹配的技能名 target_skill（无法归类则为 null）、"
        "置信度 confidence（0~1）、简短理由 reason。"
    )


class LlmIntentRecognizer:
    """实现 IntentRecognizer 端口。"""

    def __init__(self, llm: Any) -> None:
        self._structured = llm.with_structured_output(IntentClassification)

    async def recognize(
        self,
        messages: list[dict[str, str]],
        skills: list[SkillConfig],
    ) -> IntentClassification:
        catalog = "\n".join(f"- {s.name}: {s.description}" for s in skills)
        prompt = _build_classify_prompt(catalog, messages)
        result: IntentClassification = await self._structured.ainvoke(prompt)
        return result
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_llm_intent_recognizer -v`
Expected: PASS（2 个用例）

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/ai/llm_intent_recognizer.py tests/test_llm_intent_recognizer.py
git commit -m "feat: 新增 LlmIntentRecognizer（with_structured_output 单次结构化调用）"
```

---

## Task 7: build_agent_registry（基础设施装配多技能 Agent）

遍历 `SkillConfig` 列表：每 skill → `AgentPromptConfig(identity, skill).render()` → `create_react_agent` → `LangChainAgentService`；再建 `GENERAL_SKILL` 兜底 Agent，一起装进 `AgentRegistry`。

> **分层说明（设计 §12 遗留债）**：本文件在 `infrastructure/ai/`，需 import `interfaces.ai.react_agent.LangChainAgentService`。`LangChainAgentService` 本应在 infrastructure（现误置于 interfaces），此 import 属已知遗留债，待其迁移后自然干净——本计划不修。

**Files:**
- Create: `src/infrastructure/ai/skill_agent_builder.py`
- Test: `tests/test_skill_agent_builder.py`

**Interfaces:**
- Consumes: `AgentIdentity`、`SkillConfig`、`AgentPromptConfig`（domain）、`GENERAL_SKILL`（Task 4）、`create_react_agent`（`infrastructure.ai.agent_factory`）、`LangChainAgentService`（`interfaces.ai.react_agent`）、`LLMClientFactory`。
- Produces: `build_agent_registry(*, identity: AgentIdentity, skills: list[SkillConfig], general_skill: SkillConfig, llm_factory: LLMClientFactory) -> AgentRegistry`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_skill_agent_builder.py`（用真实 `ChatDeepSeek`（假 key，不触网）构建，仅断言注册表结构，不 invoke）：

```python
"""build_agent_registry 测试——建出每技能 Agent + 兜底 general，断言结构。"""
from __future__ import annotations

import unittest

from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.skill_agent_builder import build_agent_registry
from infrastructure.config.llm_config import LLMConfig
from infrastructure.ai.llm_client_factory import LLMClientFactory


def _identity() -> AgentIdentity:
    return AgentIdentity(persona="账票助手", tones="专业简洁")


def _skills() -> list[SkillConfig]:
    return [
        SkillConfig(name="auditing", description="发票稽核", task_instructions="稽核"),
        SkillConfig(name="receiving", description="发票收票", task_instructions="收票"),
    ]


class BuildAgentRegistryTest(unittest.TestCase):
    def test_registry_has_all_skills_plus_general(self) -> None:
        # 假 key，仅构建 ChatDeepSeek 与编译图，不发起网络调用
        factory = LLMClientFactory(LLMConfig(model="deepseek-chat", api_key="sk-test"))
        registry = build_agent_registry(
            identity=_identity(),
            skills=_skills(),
            general_skill=GENERAL_SKILL,
            llm_factory=factory,
        )
        self.assertEqual(registry.available(), {"auditing", "receiving", "general"})
        # 兜底存在：get 未知技能回落 general，不抛错
        self.assertIsNotNone(registry.get("不存在"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_skill_agent_builder -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'infrastructure.ai.skill_agent_builder'`

- [ ] **Step 3: 写最小实现**

创建 `src/infrastructure/ai/skill_agent_builder.py`：

```python
"""多技能 Agent 装配 —— 从 SkillConfig 列表建「每技能一个 Agent」+ 兜底 general。"""
from __future__ import annotations

import logging

from application.ports.agent_service import AgentService
from application.services.agent_registry import AgentRegistry
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.agent_prompt_config import AgentPromptConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.agent_factory import create_react_agent
from infrastructure.ai.llm_client_factory import LLMClientFactory
# 注：LangChainAgentService 现误置于 interfaces/ai（设计 §12 遗留债）
from interfaces.ai.react_agent import LangChainAgentService

logger = logging.getLogger("ai-finance")


def _build_one(identity: AgentIdentity, skill: SkillConfig, llm) -> AgentService:
    """把单个技能装配为一个可运行的 AgentService。"""
    prompt = AgentPromptConfig(agent_identity=identity, skill=skill).render()
    agent = create_react_agent(llm=llm, tools=[], system_prompt=prompt)
    return LangChainAgentService(agent)


def build_agent_registry(
    *,
    identity: AgentIdentity,
    skills: list[SkillConfig],
    general_skill: SkillConfig,
    llm_factory: LLMClientFactory,
) -> AgentRegistry:
    """遍历技能建 Agent，再建兜底 general，装进 AgentRegistry。"""
    llm = llm_factory.create_llm()
    entries: dict[str, tuple[SkillConfig, AgentService]] = {}
    for skill in skills:
        entries[skill.name] = (skill, _build_one(identity, skill, llm))
    entries[general_skill.name] = (general_skill, _build_one(identity, general_skill, llm))
    logger.info("已装配 %d 个技能 Agent（含兜底 %s）", len(entries), general_skill.name)
    return AgentRegistry(entries, fallback=general_skill.name)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `uv run python -m unittest tests.test_skill_agent_builder -v`
Expected: PASS（1 个用例）

> 若真实 `ChatDeepSeek` 构建或 `create_agent` 编译需要网络导致失败，退化断言：仅测试 `AgentRegistry` 装配逻辑已在 Task 4 覆盖，此处可 `skipTest` 并在交付说明中注明。但正常情况下构建不触网。

- [ ] **Step 5: 提交**

```bash
git add src/infrastructure/ai/skill_agent_builder.py tests/test_skill_agent_builder.py
git commit -m "feat: 新增 build_agent_registry 装配多技能 Agent + 兜底 general"
```

---

## Task 8: bootstrap 接线 + 非流式回填 + 集成测试 + 协议文档同步

把 bootstrap 装配的单例从「单个 agent」换成 `RoutingAgentService`；`ChatResponse` 增加 `routed_skill` 并在路由回填；集成测试验证首帧 routing、兜底路径、分类器故障降级；回填 SSE 设计文档 §5.2/§5.3。

**Files:**
- Modify: `src/bootstrap/container.py`（装配 RoutingAgentService）
- Modify: `src/interfaces/http/schemas.py`（`ChatResponse.routed_skill`）
- Modify: `src/interfaces/http/agent_router.py`（非流式回填 `routed_skill`）
- Modify: `docs/superpowers/specs/2026-07-19-agent-sse-streaming-design.md`（§5.2/§5.3 补 routing）
- Test: `tests/test_routing_integration.py`

**Interfaces:**
- Consumes: `build_agent_registry`（Task 7）、`LlmIntentRecognizer`（Task 6）、`RoutingPolicy`（Task 3）、`RoutingConfig`（Task 2）、`GENERAL_SKILL`（Task 4）、`get_agent_service`（SSE 计划 Task 3）。
- Produces: `Container.agent_service` 现为 `RoutingAgentService`；`ChatResponse.routed_skill: str | None = None`。

- [ ] **Step 1: 写失败集成测试**

创建 `tests/test_routing_integration.py`（`httpx.ASGITransport` + 注入 stub `AgentService=RoutingAgentService`，不打真实 LLM）：

```python
"""路由端到端集成——首帧 routing、兜底、分类器故障降级仍 200。"""
from __future__ import annotations

import asyncio
import json
import unittest
from collections.abc import AsyncIterator

import httpx

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.services.agent_registry import AgentRegistry
from application.services.routing_agent_service import RoutingAgentService
from bootstrap.dependencies import get_agent_service
from bootstrap.main import app
from domain.services.routing_policy import RoutingPolicy
from domain.shared.general_skill import GENERAL_SKILL
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig


class _StubWorker:
    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply=self.tag)

    async def stream(self, request: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        yield AgentStreamEvent(event_type="token", content=self.tag)
        yield AgentStreamEvent(event_type="done")


class _StubRecognizer:
    def __init__(self, result, *, raise_exc=False) -> None:
        self._result, self._raise = result, raise_exc

    async def recognize(self, messages, skills) -> IntentClassification:
        if self._raise:
            raise RuntimeError("炸")
        return self._result


def _routing_service(recognizer) -> RoutingAgentService:
    registry = AgentRegistry(
        {
            "auditing": (SkillConfig(name="auditing", description="稽核", task_instructions="稽核"), _StubWorker("auditing")),
            "general": (GENERAL_SKILL, _StubWorker("general")),
        },
        fallback="general",
    )
    return RoutingAgentService(recognizer, RoutingPolicy(RoutingConfig()), registry)


def _client(recognizer) -> httpx.AsyncClient:
    app.dependency_overrides[get_agent_service] = lambda: _routing_service(recognizer)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _stream_events(client, recognizer=None) -> list[str]:
    types: list[str] = []
    async with client.stream("POST", "/agent/chat/stream", json={"messages": [{"role": "user", "content": "帮我稽核"}]}) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                types.append(line.split(":", 1)[1].strip())
    return types


class RoutingIntegrationTest(unittest.TestCase):
    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_first_frame_is_routing(self) -> None:
        async def run() -> None:
            async with _client(_StubRecognizer(IntentClassification(target_skill="auditing", confidence=0.9))) as client:
                types = await _stream_events(client)
                self.assertEqual(types[0], "routing")
                self.assertIn("done", types)

        asyncio.run(run())

    def test_classifier_failure_still_200_and_degrades(self) -> None:
        async def run() -> None:
            async with _client(_StubRecognizer(None, raise_exc=True)) as client:
                types = await _stream_events(client)
                self.assertEqual(types[0], "routing")  # 降级仍先发 routing（general）

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `uv run python -m unittest tests.test_routing_integration -v`
Expected: 初始应能通过（复用 SSE 计划已就绪的端点 + 本计划前序任务的 RoutingAgentService）。若 SSE 计划未先落地，会 `ImportError`/404。**确认 SSE 计划已完成后**本测试即验证路由链路。

- [ ] **Step 3: bootstrap 装配 RoutingAgentService**

在 `src/bootstrap/container.py` 的 `build_container` 中，替换「4. 创建 ReAct Agent / 5. 包装为 AgentService」两步为装配路由服务（需要 `identity`；MVP 从传入参数或默认 `AgentIdentity` 取，`skills` 从传入参数取，二者由调用方 lifespan 从预热仓库提供）。新增 `build_container` 关键字参数 `identity: AgentIdentity | None` 与 `skills: list[SkillConfig] | None`，装配示意：

```python
from domain.shared.general_skill import GENERAL_SKILL
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.routing_config import RoutingConfig
from infrastructure.ai.llm_intent_recognizer import LlmIntentRecognizer
from infrastructure.ai.skill_agent_builder import build_agent_registry
from application.services.routing_agent_service import RoutingAgentService

    # 4. 装配多技能 Agent 注册表 + 意图识别 + 路由裁决
    registry = build_agent_registry(
        identity=identity or _DEFAULT_IDENTITY,
        skills=skills or [],
        general_skill=GENERAL_SKILL,
        llm_factory=llm_factory,
    )
    recognizer = LlmIntentRecognizer(llm_factory.create_llm())
    policy = RoutingPolicy(RoutingConfig())

    # 5. 组装为对外唯一 AgentService 入口
    container.agent_service = RoutingAgentService(recognizer, policy, registry)
```

在 `src/bootstrap/main.py` 的 `lifespan` 预热单例处（SSE 计划 Task 3 已加）把 identity/skills 传入：

```python
    container = await build_container(
        config=llm_repo.get(),
        identity=agent_repo.get("agent-identity"),
        skills=skill_repo.get("skill-configs"),
        skip_db=True,
    )
    app.state.agent_service = container.agent_service
```

> `_DEFAULT_IDENTITY` 为 container 模块内一个最小 `AgentIdentity` 常量（`persona="AI 账票助手", tones="专业简洁"`），仅在未传 identity 时兜底。

- [ ] **Step 4: ChatResponse 回填 routed_skill**

在 `src/interfaces/http/schemas.py` 的 `ChatResponse` 增加字段：

```python
    routed_skill: str | None = None
```

在 `src/interfaces/http/agent_router.py` 的非流式 `chat` 回填：

```python
    return ChatResponse(
        reply=resp.reply,
        thread_id=resp.thread_id,
        tool_calls_count=resp.tool_calls_count,
        routed_skill=resp.routed_skill,
    )
```

- [ ] **Step 5: 运行集成测试 + 全量回归**

Run: `uv run python -m unittest tests.test_routing_integration -v`
Expected: PASS（2 个用例）

Run: `uv run python -m unittest discover -s tests`
Expected: OK（全绿）

- [ ] **Step 6: 同步 SSE 协议文档**

编辑 `docs/superpowers/specs/2026-07-19-agent-sse-streaming-design.md`：
- §5.2 事件类型表增加一行：`routing | 本轮对话转接到的技能 | 转接说明文本 | 目标技能名`。
- §5.3 `data` JSON schema 的 `event_type` 枚举补 `routing`，并注明新增可选字段 `skill_name: string | null`。

- [ ] **Step 7: 提交**

```bash
git add src/bootstrap/container.py src/bootstrap/main.py src/interfaces/http/schemas.py src/interfaces/http/agent_router.py docs/superpowers/specs/2026-07-19-agent-sse-streaming-design.md tests/test_routing_integration.py
git commit -m "feat: bootstrap 装配 RoutingAgentService 单例，非流式回填 routed_skill，同步 SSE 协议"
```

---

## Task 9: 端到端手动验证（真实启动）

**Files:** 无（仅运行验证）

- [ ] **Step 1: 启动服务**（需 `config/config.json` + Nacos 可达；否则跳过并注明）

Run: `uv run python main.py`
Expected: 日志出现 `已装配 N 个技能 Agent（含兜底 general）` 与 `AgentService 已预热（单例）`。

- [ ] **Step 2: 打流式端点确认首帧 routing**

Run:
```bash
curl -N -X POST http://localhost:8000/agent/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"帮我稽核发票 12345"}]}'
```
Expected: 首帧 `event: routing`（`data` 含 `skill_name`），随后 worker 的 `token`/`done`。

- [ ] **Step 3: 兜底路径**

发一句与技能无关的闲聊，确认 `routing` 帧 `skill_name=general`。停止服务。

---

## Self-Review（写完计划后自查）

**1. Spec 覆盖**（对照设计 §2 目标）：
- 显式意图识别组件（对话 + 技能目录 → {技能, 置信度, 理由}）→ Task 6 `LlmIntentRecognizer` + Task 2 `IntentClassification` ✅
- `RoutingPolicy` 领域服务按阈值裁决/兜底 → Task 3 ✅
- `RoutingAgentService` 实现现有 `AgentService` 端口，interfaces 零改动 → Task 5 + Task 8（仅回填 routed_skill，端点逻辑不变）✅
- 从 skills 构建多技能注册表 + 兜底通用 Agent → Task 4/Task 7 ✅
- 流式追加 `routing` 事件 → Task 1 + Task 5（stream 首帧）+ Task 8（协议文档同步）✅
- 任一识别环节失败安全降级兜底 → Task 5 `_route` try/except + `RoutingPolicy` 兜底 + `AgentRegistry` fail-fast ✅
- DDD 校验：domain 三组件无框架 import → Task 2/3 纯 Pydantic/stdlib ✅

**2. 占位符扫描**：无 TODO / 无「适当处理」；每个代码步骤给出完整代码。Task 8 Step 3 的 container 改造以「替换第 4/5 步」明确锚定既有结构，非占位。

**3. 类型一致性**：`recognize(messages, skills) -> IntentClassification`（端口 Task 4）与实现（Task 6）、调用（Task 5 `_route`）一致；`RoutingPolicy.decide(c, available)`（Task 3）与调用（Task 5）一致；`AgentRegistry.get/available/catalog`（Task 4）与 `RoutingAgentService`/`build_agent_registry` 使用一致；`RoutingDecision.skill_name/is_fallback`（Task 2）贯穿 Task 3/5 一致；`routed_skill`（Task 1 DTO）→ Task 5 回填 → Task 8 ChatResponse 一致。

**非目标确认**（不做）：不改底层 `astream_events` 映射与 5 类基础事件（仅追加 routing）、不修 `LangChainAgentService` 分层位置、不做跨轮会话锁定、Phase 2 handoff supervisor 另起 spec、分类器不做槽位抽取。
