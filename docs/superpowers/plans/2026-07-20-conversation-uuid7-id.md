# 会话单调 UUIDv7 ID 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 会话 ID 从 uuid4 换成进程内单调 UUIDv7——同进程严格递增、hex 字典序即时间序、存储零迁移。

**Architecture:** 领域层 `domain/shared` 新增纯标准库单调 uuid7 生成器（RFC 9562 Method 1：rand_a 作 12 位毫秒内计数器）；`ConversationId` 值对象收编生成职责（`new()`）并加格式校验；聚合工厂只改一行；接口层入参加同款 pattern，非法格式在边界 422。规格见 `docs/superpowers/specs/2026-07-20-conversation-uuid7-id-design.md`。

**Tech Stack:** Python 3.11（经 `uv run`）、Pydantic v2、unittest（标准库）、FastAPI + httpx ASGITransport（路由测试）。

## Global Constraints

- 一切命令经 `uv run` 执行（系统 python3 是 3.9，不可直接用）。
- `domain` 层零第三方依赖：生成器只用 `secrets`/`threading`/`time`/`uuid` 标准库。
- 全项目 Pydantic v2 建模，禁止 `dataclasses.dataclass`。
- ID 格式校验 pattern 全局统一为 `^[0-9a-f]{32}$`（32 位小写十六进制）。
- 注释、文档、提交信息一律中文；提交信息末尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`。
- 每个 Task 结束时全量测试必须绿：`uv run python -m unittest discover -s tests`（现有 138 个用例）。

---

### Task 1: 单调 uuid7 生成器

**Files:**
- Create: `src/domain/shared/id_generator.py`
- Test: `tests/test_id_generator.py`（新建）

**Interfaces:**
- Consumes: 无（纯标准库）。
- Produces: `uuid7() -> uuid.UUID`，位于 `domain.shared.id_generator`；保证同进程严格递增、version=7、variant=RFC 4122、`.hex` 为 32 位小写十六进制。Task 2 依赖此函数。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_id_generator.py`：

```python
"""单调 uuid7 生成器测试——格式、位段、严格递增、并发唯一、回拨不倒退。"""
from __future__ import annotations

import threading
import time
import unittest
from uuid import RFC_4122

from domain.shared.id_generator import uuid7


class IdGeneratorTest(unittest.TestCase):
    def test_hex_format(self) -> None:
        self.assertRegex(uuid7().hex, r"^[0-9a-f]{32}$")

    def test_version_and_variant(self) -> None:
        u = uuid7()
        self.assertEqual(u.version, 7)
        self.assertEqual(u.variant, RFC_4122)

    def test_strictly_increasing_sequence(self) -> None:
        ids = [uuid7() for _ in range(5000)]
        for a, b in zip(ids, ids[1:]):
            self.assertLess(a.int, b.int)

    def test_hex_sort_order_matches_generation_order(self) -> None:
        hexes = [uuid7().hex for _ in range(5000)]
        self.assertEqual(hexes, sorted(hexes))

    def test_threaded_generation_unique_and_ordered(self) -> None:
        buckets: list[list[int]] = [[] for _ in range(8)]

        def worker(bucket: list[int]) -> None:
            for _ in range(2000):
                bucket.append(uuid7().int)

        threads = [threading.Thread(target=worker, args=(b,)) for b in buckets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        flat = [x for b in buckets for x in b]
        self.assertEqual(len(flat), len(set(flat)))  # 跨线程全局无重复
        for b in buckets:
            self.assertEqual(b, sorted(b))  # 各线程内严格递增

    def test_clock_rollback_and_counter_overflow_never_regress(self) -> None:
        # 把生成器状态拨到未来 10 秒，模拟时钟回拨；连续生成压满计数器走借毫秒路径。
        from domain.shared import id_generator as gen

        saved = (gen._last_ms, gen._counter)
        future_ms = time.time_ns() // 1_000_000 + 10_000
        gen._last_ms, gen._counter = future_ms, 0
        try:
            ids = [uuid7() for _ in range(5000)]
            for a, b in zip(ids, ids[1:]):
                self.assertLess(a.int, b.int)          # 永不倒退
            self.assertGreaterEqual(ids[0].int >> 80, future_ms)  # 时间戳段沿用未来值
        finally:
            gen._last_ms, gen._counter = saved


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_id_generator -v`
Expected: 全部 ERROR，报 `ModuleNotFoundError: No module named 'domain.shared.id_generator'`。

- [ ] **Step 3: 写最小实现**

创建 `src/domain/shared/id_generator.py`：

```python
"""进程内单调 UUIDv7 生成器（RFC 9562, Method 1）。

纯标准库实现，零第三方依赖——供各子域生成趋势递增的聚合标识。
单调性：同进程严格递增（48 位毫秒时间戳 + rand_a 作 12 位毫秒内计数器）；
时钟回拨时沿用上次时间戳继续计数，计数器打满则借下一毫秒，ID 永不倒退。
不可枚举性：每个 ID 含 62 位安全随机（rand_b）。
"""
from __future__ import annotations

import secrets
import threading
import time
from uuid import UUID

_lock = threading.Lock()
_last_ms = 0
_counter = 0

_MAX_COUNTER = 0xFFF  # 12 位计数器上限：单毫秒 4096 个


def uuid7() -> UUID:
    """生成一个单调递增的 UUIDv7。"""
    global _last_ms, _counter
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms > _last_ms:
            _last_ms = ms
            _counter = 0
        else:  # 同毫秒并发或时钟回拨：沿用上次时间戳递增计数
            _counter += 1
            if _counter > _MAX_COUNTER:
                _last_ms += 1  # 借下一毫秒
                _counter = 0
        value = (
            (_last_ms & 0xFFFF_FFFF_FFFF) << 80  # unix_ts_ms: bit 80-127
            | 0x7 << 76                          # version 7:  bit 76-79
            | _counter << 64                     # 计数器:     bit 64-75
            | 0b10 << 62                         # variant:    bit 62-63
            | secrets.randbits(62)               # rand_b:     bit 0-61
        )
        return UUID(int=value)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_id_generator -v`
Expected: 6 个用例全部 ok。

- [ ] **Step 5: 全量回归 + 提交**

Run: `uv run python -m unittest discover -s tests` → 全绿（138 + 6）。

```bash
git add src/domain/shared/id_generator.py tests/test_id_generator.py
git commit -m "feat: 领域层新增进程内单调 UUIDv7 生成器（纯标准库）

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: ConversationId 加固（pattern 校验 + new() 工厂）

**Files:**
- Modify: `src/domain/conversation/value_objects.py:10-14`（ConversationId 类）
- Modify: `tests/test_conversation_value_objects.py:19-20`（改造 ID 断言）
- Modify: `tests/test_conversation_aggregate.py:73`（夹具改合法 hex）
- Modify: `tests/test_conversation_repository.py:82`（夹具改合法 hex）

**Interfaces:**
- Consumes: Task 1 的 `uuid7() -> uuid.UUID`（`from domain.shared.id_generator import uuid7`）。
- Produces: `ConversationId.new() -> ConversationId`；`ConversationId.value` 仅接受 `^[0-9a-f]{32}$`。Task 3 依赖 `new()`。

> 注意：pattern 与夹具修正必须同一 commit——加了校验后 `"c1"`、`"不存在"` 立即非法，拆开提交会出现红灯中间态。

- [ ] **Step 1: 写失败测试**

`tests/test_conversation_value_objects.py` 中删除原 `test_conversation_id`（第 19-20 行），替换为三个用例：

```python
    def test_conversation_id_new_is_valid_and_increasing(self) -> None:
        a, b = ConversationId.new(), ConversationId.new()
        self.assertRegex(a.value, r"^[0-9a-f]{32}$")
        self.assertLess(a.value, b.value)  # hex 字典序 = 生成序

    def test_conversation_id_rejects_invalid(self) -> None:
        for bad in ("abc", "A" * 32, "g" * 32, "0" * 31, "0" * 33):
            with self.assertRaises(ValidationError):
                ConversationId(value=bad)

    def test_conversation_id_accepts_legacy_hex(self) -> None:
        # 存量 uuid4 hex 同为 32 位小写十六进制，必须继续可用
        self.assertEqual(ConversationId(value="0" * 32).value, "0" * 32)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_value_objects -v`
Expected: `test_conversation_id_new_is_valid_and_increasing` ERROR（无 `new` 属性）；`test_conversation_id_rejects_invalid` FAIL（当前无校验、不抛错）。

- [ ] **Step 3: 写实现**

`src/domain/conversation/value_objects.py`——`ConversationId` 类整体替换为：

```python
class ConversationId(BaseModel):
    """对话标识（uuid7 hex，32 位小写十六进制，趋势递增）。"""

    value: str = Field(pattern=r"^[0-9a-f]{32}$")
    model_config = {"frozen": True}

    @classmethod
    def new(cls) -> "ConversationId":
        """生成新标识——单调 uuid7，ID 字典序即创建时间序。"""
        return cls(value=uuid7().hex)
```

文件顶部 import 区新增（`from pydantic import BaseModel, Field` 已存在，无需动）：

```python
from domain.shared.id_generator import uuid7
```

- [ ] **Step 4: 修正两处夹具**

`tests/test_conversation_aggregate.py:73`：

```python
            id=ConversationId(value="0" * 30 + "c1"), agent_id=_agent(),
```

`tests/test_conversation_repository.py:82`：

```python
            self.assertIsNone(await repo.get(ConversationId(value="f" * 32)))  # 合法但不存在
```

- [ ] **Step 5: 全量回归 + 提交**

Run: `uv run python -m unittest discover -s tests` → 全绿。

```bash
git add src/domain/conversation/value_objects.py tests/test_conversation_value_objects.py tests/test_conversation_aggregate.py tests/test_conversation_repository.py
git commit -m "feat: ConversationId 加 32 位 hex 校验与 new() 工厂，夹具改合法格式

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 聚合工厂切换到单调 ID

**Files:**
- Modify: `src/domain/conversation/aggregate.py:10`（删 import）、`src/domain/conversation/aggregate.py:54`（改生成）
- Modify: `tests/test_conversation_aggregate.py`（新增时间序测试）

**Interfaces:**
- Consumes: Task 2 的 `ConversationId.new()`。
- Produces: `Conversation.start()` 产出的 `id.value` 趋势递增——后续任何按 ID 排序的消费者依赖此性质。

- [ ] **Step 1: 写失败测试**

`tests/test_conversation_aggregate.py` 的 `ConversationAggregateTest` 中新增：

```python
    def test_start_ids_are_time_ordered(self) -> None:
        ids = [Conversation.start(_agent()).id.value for _ in range(20)]
        self.assertEqual(ids, sorted(ids))  # 单调 uuid7：ID 序即创建序
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_aggregate -v`
Expected: `test_start_ids_are_time_ordered` FAIL——uuid4 随机，20 个 ID 恰好有序的概率约 1/20!，可视为必然失败。

- [ ] **Step 3: 写实现**

`src/domain/conversation/aggregate.py` 第 10 行删除：

```python
from uuid import uuid4
```

第 54 行（`Conversation.start()` 内）：

```python
            id=ConversationId(value=uuid4().hex),
```

改为：

```python
            id=ConversationId.new(),
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_aggregate -v`
Expected: 8 个用例全部 ok。

- [ ] **Step 5: 全量回归 + 提交**

Run: `uv run python -m unittest discover -s tests` → 全绿。

```bash
git add src/domain/conversation/aggregate.py tests/test_conversation_aggregate.py
git commit -m "feat: 会话聚合改用 ConversationId.new()——ID 趋势递增

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 接口层入参格式校验（非法 conversation_id 直接 422）

**Files:**
- Modify: `src/interfaces/conversation/schemas.py:7-11`（SendMessageBody）
- Modify: `tests/test_conversation_router.py`（新增 422 用例）

**Interfaces:**
- Consumes: 无（pattern 字面量与 Task 2 保持一致：`^[0-9a-f]{32}$`）。
- Produces: `/conversations/messages` 对格式非法的 `conversation_id` 返回 422；`None` 与合法值行为不变。

- [ ] **Step 1: 写失败测试**

`tests/test_conversation_router.py` 的 `ConversationRouterTest` 中新增：

```python
    def test_malformed_conversation_id_rejected_422(self) -> None:
        async def run() -> None:
            transport = httpx.ASGITransport(app=self.app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(
                    "/conversations/messages",
                    json={"content": "你好", "conversation_id": "not-a-valid-id"},
                )
                self.assertEqual(resp.status_code, 422)  # 边界拒绝，不进用例

        asyncio.run(run())
```

- [ ] **Step 2: 跑测试确认失败**

Run: `uv run python -m unittest tests.test_conversation_router -v`
Expected: 新用例 FAIL——当前无校验，stub 用例照常执行返回 200。

- [ ] **Step 3: 写实现**

`src/interfaces/conversation/schemas.py` 整个 `SendMessageBody` 改为（并把顶部 import 改成 `from pydantic import BaseModel, Field`）：

```python
class SendMessageBody(BaseModel):
    content: str
    # None = 新开对话；传值必须是 32 位小写 hex（与 ConversationId 同款约束），非法格式边界 422
    conversation_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    agent_name: str = "default_agent"
    agent_version: str = "default"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `uv run python -m unittest tests.test_conversation_router -v`
Expected: 2 个用例全部 ok（原 200 用例传的是 `conversation_id` 缺省 None，不受影响）。

- [ ] **Step 5: 全量回归 + 提交**

Run: `uv run python -m unittest discover -s tests` → 全绿。

```bash
git add src/interfaces/conversation/schemas.py tests/test_conversation_router.py
git commit -m "feat: /conversations/messages 入参 conversation_id 加格式校验，非法直接 422

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## 收尾核对（Task 4 之后）

- [ ] `uv run python -m unittest discover -s tests` 全绿（预期 138 + 10 = 148 个用例：生成器 6、值对象净增 2、聚合 1、路由 1）。
- [ ] `rg -n "uuid4" src/domain/conversation/` 无结果（生成路径已全部切换）。
- [ ] `graphify update .` 刷新知识图谱（CLAUDE.md 要求，AST-only 无 API 成本）。
