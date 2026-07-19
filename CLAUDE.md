# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言约定

- 与用户的所有对话、代码注释、文档、Git 提交信息**一律使用中文**。

## 项目简介

账票服务:处理账单发票的两大能力——**收票**(receiving)与**稽核**(auditing)。
采用 DDD 分层架构,单一限界上下文「账票 / billing」,收票与稽核为其内部业务模块。

已落地的子域:
- **Agent 对话**（`conversation/`）:Conversation 聚合根、SQLAlchemy 持久化、多轮记忆由领域层提供
- **意图路由**（`services/routing_*`）:LLM 结构化意图识别 → 置信度裁决 → 多技能 Agent 分发
- **SSE 流式输出**:`/agent/chat/stream` 逐 token 推送

## 环境与常用命令

**Python 版本坑**:系统 `python` 不存在、`python3` 是 3.9;本项目要求 **3.11**。
**一律通过 `uv run` 执行**(uv 会自动选用 3.11、建环境并以可编辑方式装入本项目),不要直接用系统 `python3`。

```bash
# 启动服务（需 Nacos + PostgreSQL 可达）
uv run python main.py

# 开发热重载
uv run uvicorn bootstrap.app:create_app --factory --reload

# 运行全部测试（138 个用例, ~31s）
uv run python -m unittest discover -s tests

# 运行单个测试(模块.类.方法)
uv run python -m unittest tests.test_conversation_aggregate.ConversationAggregateTest.test_start_emits_started_event

# 新增依赖(接入某框架时,放到对应层使用)
uv add <package>
```

- `uv.lock` 需提交;`.venv` 已在 `.gitignore` 中。
- 测试当前用标准库 `unittest`(零依赖)。若改用 pytest,先 `uv add --dev pytest`。

## 启动依赖

服务需要 **Nacos**（配置中心）+ **PostgreSQL**（持久化）。Nacos 中需存在以下配置项（`namespace=ai-finance`, `group=AI-FINANCE`）:

| data_id | 格式 | 说明 |
|---------|------|------|
| `postgres` | YAML | 数据库连接 `db_dsn` + 连接池参数 |
| `llm-config` | YAML | LLM `api_key`、`model`、`base_url` |
| `agent-identity` | YAML | Agent 身份定义（`persona`、`tones`） |
| `skill-configs` | YAML | 技能列表（`name`、`description`、`task_instructions`） |

## 架构

### 分层与依赖方向(DDD 核心约束)

`src/` 采用**扁平布局**:四个 DDD 层 + `bootstrap` 各自是 `src/` 下的**顶层包**(无统一父包),
因此导入形如 `from domain... / from application... / from infrastructure... / from interfaces...`。

| 层 | 目录 | 职责 |
|---|---|---|
| 用户接口层 | `src/interfaces/` | API 路由、请求/响应模型、依赖注入、CLI(入站适配器) |
| 应用层 | `src/application/` | 用例/应用服务、命令与查询、DTO、事务编排 |
| 领域层 | `src/domain/` | 聚合根、实体、值对象、领域服务、领域事件、仓储接口 |
| 基础设施层 | `src/infrastructure/` | 仓储实现、ORM、事件总线、外部适配、配置、DB |
| 启动/组合根 | `src/bootstrap/` | 装配依赖、注册事件订阅、创建并启动服务 |

**依赖方向铁律**:`interfaces → application → domain ← infrastructure`。
`domain` 是业务内核,**不依赖任何其他层**;基础设施靠"实现领域定义的接口(端口)"接入。

### 组合根 bootstrap

- `bootstrap/container.py` 的 `build_container()`(async):**单一装配出口**,一次性完成 Nacos → 配置仓库预热 → DatabaseManager → Agent 单例全链装配;资源关闭由 `AsyncExitStack` 逆序执行(`Container.shutdown()`)。`Container` 是 frozen Pydantic 模型,`agent_service` 字段标 application 端口类型。
- `bootstrap/container.py` 的 `build_conversation_use_case(engine, agent_service)`:对话用例装配工厂,产出 `SendMessageUseCase`。
- `bootstrap/app.py` 的 `create_app(container=None)`:FastAPI 应用工厂;生产路径在 lifespan 内 `await build_container()` + 建对话表 + 装配对话用例;测试路径传入预制 Container(由调用方负责 shutdown)。
- `bootstrap/main.py` 的 `main()`:仅以 uvicorn factory 模式运行 `bootstrap.app:create_app`。
- FastAPI 的 DI 胶水(`Depends` provider)位于 `interfaces/api/dependencies.py`:签名只标 domain/application 端口类型,函数体从 `app.state.container` 或 `app.state` 取字段。
- **已删除** `bootstrap/dependencies.py`（旧的 infrastructure 级 DI,已归入 interfaces/api/dependencies.py）。
- 根目录 `main.py` 是**免配置启动器**,仅把 `src` 加入路径后委托给 `bootstrap.main:main`;正式入口是 `pyproject.toml` 里的 `ai-finance` 脚本。

### API 路由

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/agent/identity` | Agent 身份定义（只读） |
| GET | `/agent/skills` | 可用技能列表（只读） |
| POST | `/agent/chat` | 非流式对话（含 `routed_skill` 回填） |
| POST | `/agent/chat/stream` | SSE 流式对话（首帧 `routing`→逐帧 `token`→`done`） |
| POST | `/conversations/messages` | 对话消息（`conversation_id` 续聊,记忆由 Conversation 聚合提供） |

### 核心链路

**Agent 对话链路**（`/agent/chat[/stream]`）:
HTTP → `ChatRequest.to_agent_request()` → `RoutingAgentService` → `LlmIntentRecognizer` 识别意图 → `RoutingPolicy` 置信度裁决 → `AgentRegistry` 分发到对应技能 Agent（兜底 `general`） → `AgentResponse`/`AgentStreamEvent` → HTTP 响应/SSE 帧

**对话持久化链路**（`/conversations/messages`）:
HTTP → `SendMessageBody` → `SendMessageCommand` → `SendMessageUseCase.execute()` → `Conversation.start()/.post_user_message()` → `ContextWindowPolicy` 裁剪窗口 → `AgentService.run()` 无状态执行 → `Conversation.record_assistant_message()` → `ConversationRepository.save()` append-only 落库 → `DomainEventPublisher.publish()` 发事件 → `ChatResult`

### 业务子域

| 子域 | 各层位置 | 说明 |
|------|----------|------|
| 对话 (Conversation) | `domain/conversation/`, `application/conversation/`, `infrastructure/conversation/`, `interfaces/conversation/` | 聚合根 + SQLAlchemy append-only 仓储 + 窗口策略 |
| Agent 路由 | `domain/services/routing_policy.py`, `domain/value_objects/intent.py`, `application/services/routing_agent_service.py`, `infrastructure/ai/llm_intent_recognizer.py` | 意图识别 → 置信度裁决 → 多技能分发 |
| AI 基础设施 | `infrastructure/ai/` | `LLMClientFactory`、`create_react_agent`、`tool_adapter`、`skill_agent_builder` |

- **跨模块只经领域事件通信**(进程内 message bus),严禁模块间直接 import/调用。

## DDD 规范(生成代码时必须遵循)

1. **依赖方向**:`domain` 不得 import `application/infrastructure/interfaces`,也不得 import 任何框架或 ORM(FastAPI、SQLAlchemy、Pydantic 等);依赖只能指向 `domain`。
2. **仓储**:接口定义在 `domain`,实现放 `infrastructure`;应用层依赖接口而非实现。
3. **聚合**:聚合根是一致性与事务边界;外部只持聚合根引用,不直接操作其内部实体;一个用例原则上只修改一个聚合。
4. **值对象**:不可变(`frozen`),以相等性比较;把业务约束(金额、税号、发票代码等)封装为值对象,不用裸 `str/Decimal` 到处传。
5. **领域事件**:聚合内产生事件表达"已发生的事实";跨模块解耦只经领域事件。
6. **应用层只编排**:用例取聚合 → 调领域方法 → 经事务提交 → 发事件;**业务规则写在 domain**(实体/值对象/领域服务),不写在应用层。
7. **领域服务**:承载跨多个聚合、无自然归属的领域逻辑(如稽核规则引擎),无状态。
8. **接口层只翻译**:把 HTTP/CLI 请求转成命令/查询并调用应用层;不含业务逻辑,不直接碰 domain 内部或数据库。
9. **依赖注入集中在 bootstrap**:各层通过构造函数参数接收依赖,不在层内 `new` 具体实现。
10. **统一语言**:命名对齐业务术语(发票 Invoice、稽核 AuditCase、收票 …)。
11. **Pydantic 优先**:生成代码时**必须使用 Pydantic v2** 定义模型（实体、值对象、DTO、配置等），**禁止使用** `dataclasses.dataclass`。Pydantic 提供原生不可变(`frozen`)、类型校验、JSON 序列化等能力，dataclass 无法等价替代。例外：仅当需要兼容第三方库的 dataclass 接口时（如 LangChain 工具装饰器），经确认后方可使用。

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| Web 框架 | **FastAPI** 0.139 | 入站适配器,置于 `interfaces` |
| SSE | **sse-starlette** | `/agent/chat/stream` 流式推送 |
| ORM | **SQLAlchemy 2.0** (async) | asyncpg 异步驱动 + psycopg2-binary 同步驱动 |
| 数据建模 | **Pydantic v2** | 全项目统一使用（`domain` 实体/值对象、`application` DTO、`interfaces` 请求/响应、`infrastructure` 配置） |
| AI | **LangChain / LangGraph** | ReAct Agent + `with_structured_output` 结构化意图识别 |
| LLM | **ChatDeepSeek** | 通过 LangChain 适配 |
| 配置中心 | **Nacos** (gRPC) | 配置拉取 + watcher 热更新 |
| 运行时 | **greenlet** | SQLAlchemy async 必需 |
| 测试 | **unittest** (标准库) | 异步用 `asyncio.run()`;仓储用 `aiosqlite` 内存库 |
| 数据库迁移 | **Alembic**（计划,尚未接入） | |
| 包管理 | **uv** | Python 3.11 环境 + 依赖锁定 |

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
