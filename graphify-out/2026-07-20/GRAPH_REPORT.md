# Graph Report - ai-finance  (2026-07-20)

## Corpus Check
- 150 files · ~39,681 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1106 nodes · 2055 edges · 88 communities (61 shown, 27 thin omitted)
- Extraction: 71% EXTRACTED · 29% INFERRED · 0% AMBIGUOUS · INFERRED: 594 edges (avg confidence: 0.6)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0bd5f2fc`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Intent Routing & Agent Registry
- Conversation Use Case & Persistence
- Agent Entity, DTO & Service Ports
- HTTP SSE Streaming & Agent Router
- Infrastructure AI Tools & Adapters
- Agent Config API Routes
- Conversation REST Router & Schemas
- Nacos Config Repository Ports
- Conversation Aggregate & Domain Events
- Conversation Value Objects
- Domain Shared AI Tools
- Domain Value Objects (Agent Identity, Skill)
- Agent HTTP Router Interface
- Skill Config & Agent Builder
- Nacos Client Infrastructure
- SSE Encoder & HTTP Schemas
- Agent Service Test Support
- Skill Lookup & Tool Registry
- LLM Config & Client Factory
- Bootstrap Container Tests
- End-to-End Integration Tests
- Routing Integration Tests
- Nacos Repository Implementation Tests
- Bootstrap App Factory Tests
- LLM Intent Recognizer Tests
- Tool Adapter Tests
- Routing Policy Tests
- Domain Prompts & General Skills
- Database & Config Infrastructure
- Agent Service Port Tests
- Test Support Fixtures
- Domain Event Tests
- Design Docs: Agent SSE Streaming
- Design Docs: Conversation Aggregate
- Nacos Client Infrastructure Tests
- Project CLAUDE.md Conventions
- Design Docs: Intent Routing
- LLM Client Factory Infrastructure
- Agent Router Tool Domain
- Database Config Infrastructure
- Conversation Repository Implementation
- Project Config, Docker & README
- Agent DTO & Application Services
- Conversation Event Publisher Infrastructure
- Design Docs: Bootstrap Composition Root
- Design Docs: Conversation Persistence
- LLM Client Factory Tests
- Send Message Use Case Tests
- Application Entry Point & Main
- Infrastructure Config (DB, LLM)
- Domain Prompts Value Objects
- Nacos Client Lifecycle Tests
- Conversation App Init
- DTO Package Init
- Application Layer Init
- Application Ports Init
- Bootstrap Package Init
- Conversation Domain Init
- Domain Layer Init
- Domain Services Init
- General Skill Domain
- Domain Shared Init
- Conversation Infra Init
- Infrastructure Layer Init
- Infrastructure Ports Init
- AI Agent Interface Init
- AI Interface Init
- AI LLM Interface Init
- API Interface Init
- API Routes Init
- Conversation Interface Init
- HTTP Interface Init
- Interfaces Layer Init
- ORM Interface Init
- Package Metadata
- uuid7
- InterfacesApiTest
- 会话唯一 ID 设计：进程内单调 UUIDv7
- ConversationRepository
- DispatchToSkillTool
- Global Constraints
- README.md

## God Nodes (most connected - your core abstractions)
1. `AgentRequest` - 73 edges
2. `SkillConfig` - 50 edges
3. `AgentResponse` - 47 edges
4. `IntentClassification` - 42 edges
5. `Conversation` - 41 edges
6. `AgentStreamEvent` - 40 edges
7. `NacosClient` - 37 edges
8. `ConversationId` - 30 edges
9. `AgentId` - 30 edges
10. `Container` - 29 edges

## Surprising Connections (you probably didn't know these)
- `ConversationRouterTest` --uses--> `SendMessageCommand`  [INFERRED]
  tests/test_conversation_router.py → src/application/conversation/commands.py
- `_FakeRepo` --uses--> `SendMessageCommand`  [INFERRED]
  tests/test_send_message_use_case.py → src/application/conversation/commands.py
- `ConversationRouterTest` --uses--> `ChatResult`  [INFERRED]
  tests/test_conversation_router.py → src/application/conversation/commands.py
- `_FakeAgent` --uses--> `SendMessageUseCase`  [INFERRED]
  tests/test_send_message_use_case.py → src/application/conversation/send_message.py
- `_FakePublisher` --uses--> `SendMessageUseCase`  [INFERRED]
  tests/test_send_message_use_case.py → src/application/conversation/send_message.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Bootstrap 组合根重构模块** — claude_md_bootstrap_composition_root, claude_md_container_pydantic, claude_md_build_container, claude_md_create_app_factory, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_bootstrap_design, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_container_pydantic_model, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_app_state_container, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_di_provider_interfaces, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_async_exit_stack, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_get_agent_service_di, docs_superpowers_specs_2026_07_19_bootstrap_composition_root_design_all_routers, docs_superpowers_plans_2026_07_19_bootstrap_composition_root_bootstrap_composition_root_plan [EXTRACTED 1.00]
- **对话 (Conversation) 子域全栈模块** — docs_superpowers_specs_2026_07_19_conversation_aggregate_design_conversation_subdomain_design, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_conversation_aggregate, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_send_message_use_case, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_context_window_policy, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_domain_event_model, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_conversation_repository_port, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_domain_event_publisher_port, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_langgraph_stateless, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_pydantic_private_attr_aggregate, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_append_only_messages, docs_superpowers_specs_2026_07_19_conversation_aggregate_design_windowed_load, docs_superpowers_plans_2026_07_19_conversation_aggregate_conversation_aggregate_plan, docs_superpowers_plans_2026_07_19_conversation_aggregate_sqlalchemy_repository_implementation, docs_superpowers_plans_2026_07_19_conversation_aggregate_in_memory_event_publisher [EXTRACTED 1.00]
- **Agent 动态路由与意图识别模块** — docs_superpowers_specs_2026_07_19_intent_routing_design_intent_routing_design, docs_superpowers_specs_2026_07_19_intent_routing_design_intent_recognizer, docs_superpowers_specs_2026_07_19_intent_routing_design_routing_policy, docs_superpowers_specs_2026_07_19_intent_routing_design_routing_agent_service, docs_superpowers_specs_2026_07_19_intent_routing_design_agent_registry, docs_superpowers_specs_2026_07_19_intent_routing_design_general_skill, docs_superpowers_specs_2026_07_19_intent_routing_design_llm_intent_recognizer, docs_superpowers_specs_2026_07_19_intent_routing_design_routing_config, docs_superpowers_specs_2026_07_19_intent_routing_design_intent_classification, docs_superpowers_specs_2026_07_19_intent_routing_design_routing_decision, docs_superpowers_plans_2026_07_19_intent_routing_intent_routing_plan [EXTRACTED 1.00]

## Communities (88 total, 27 thin omitted)

### Community 0 - "Intent Routing & Agent Registry"
Cohesion: 0.08
Nodes (19): build_container(), 构建并返回组合根容器(async 全链装配)。      任一步失败时,AsyncExitStack 逆序回收已启动资源后异常上抛(fail-fast)。, 路由裁决领域服务 —— 无状态，脱离 LLM 可单测。, 置信度阈值裁决：低置信/无匹配/不在可路由集 → 兜底。, RoutingPolicy, IntentClassification, BaseModel, 意图识别与路由裁决的值对象（不可变，零框架依赖）。 (+11 more)

### Community 1 - "Conversation Use Case & Persistence"
Cohesion: 0.09
Nodes (20): ChatResult, BaseModel, 对话用例的命令与结果 DTO（Pydantic v2）。, SendMessageCommand, AgentId, 对话路由 —— POST /conversations/messages。接口层只翻译。, send_message(), ChatResultResponse (+12 more)

### Community 2 - "Agent Entity, DTO & Service Ports"
Cohesion: 0.13
Nodes (10): 技能配置仓储。      每个 key 对应一个 ``SkillConfig`` 列表（一个 Agent 可关联多个技能）。, 获取指定 key 的技能配置列表。          Args:             key: 配置键（如 ``"skill-configs"``）。, 注册技能配置变更回调。          Args:             callback: 接收新的 SkillConfig 列表的回调函数。, SkillConfigRepository, BaseModel, SkillConfig, NacosSkillConfigRepository, SkillConfig 的 Nacos 适配器 —— 实现 domain 层的 SkillConfigRepository 端口。  从 Nacos YAML (+2 more)

### Community 3 - "HTTP SSE Streaming & Agent Router"
Cohesion: 0.08
Nodes (25): AIMessage, HumanMessage, _build_config(), _count_tool_calls(), _extract_last_ai_content(), LangChainAgentService, _map_event(), Any (+17 more)

### Community 4 - "Infrastructure AI Tools & Adapters"
Cohesion: 0.05
Nodes (35): 10. 测试策略(unittest,不依赖真 Postgres), 11. 非目标(YAGNI)与演进预留, 1. 背景与目标, 2. 关键决策(已与用户确认), 3. 范围, 4. 架构总览, 5.1 状态(随 checkpoint 持久化), 5.2 RoutingMiddleware(自研) (+27 more)

### Community 5 - "Agent Config API Routes"
Cohesion: 0.12
Nodes (10): AgentService, Protocol, AI Agent 服务端口——定义 Agent 调用的抽象契约。  应用层依赖此端口，基础设施层提供 LangChain 实现。, Agent 服务抽象端口。      定义 Agent 的标准调用方式：     - run: 同步/非流式调用，返回完整结果。     - stream: 异, 非流式调用 Agent，返回完整结果。          Args:             request: 包含消息列表和可选 thread_id 的请求。, 流式调用 Agent，逐事件推送。          Args:             request: 包含消息列表和可选 thread_id 的请求。, AgentRegistry, 多技能 Agent 注册表 —— 分类器目录与可路由集合同源。 (+2 more)

### Community 6 - "Conversation REST Router & Schemas"
Cohesion: 0.13
Nodes (13): 发送消息用例 —— 对话闭环编排。业务规则在 domain，此处只编排。, SendMessageUseCase, DomainEventPublisher, Protocol, 领域事件发布端口（application）。infrastructure 提供进程内实现。, build_conversation_use_case(), AsyncEngine, 装配对话用例：SQLAlchemy 仓储 + 进程内发布器 + 窗口策略。 (+5 more)

### Community 7 - "Nacos Config Repository Ports"
Cohesion: 0.17
Nodes (7): AgentIdentity, BaseModel, NacosAgentIdentityRepository, AgentIdentity 的 Nacos 适配器 —— 实现 domain 层的 AgentIdentityRepository 端口。  从 Nacos Y, 从 Nacos 读取 AgentIdentity，支持热更新。      用法::          repo = NacosAgentIdentityRepo, 从 Nacos 拉取并注册 watcher（幂等，并发安全）。, _StubIdentityRepo

### Community 8 - "Conversation Aggregate & Domain Events"
Cohesion: 0.13
Nodes (13): BaseModel, ToolResult, _ExceptionTool, _FailingTool, _GreetTool, 工具适配器测试——验证 AITool → LangChain Tool 转换逻辑。, 适配后的 LangChain Tool 保留名称和描述。, 工具适配器测试。      适配器生成的 LangChain StructuredTool 接受单个 `input: str` 参数，     内部解析 JSO (+5 more)

### Community 9 - "Conversation Value Objects"
Cohesion: 0.12
Nodes (18): Enum, Conversation, BaseModel, 关闭对话（幂等），发 ConversationClosed。, 仓储重建：装入历史消息，不发事件、不入 pending。, 追加用户消息。不变量：status == ACTIVE 才能追加。, 追加助手回复，发 AssistantResponded。, ConversationId (+10 more)

### Community 10 - "Domain Shared AI Tools"
Cohesion: 0.11
Nodes (11): AITool, ABC, AI 工具端口——定义工具契约。  领域层不依赖任何框架（如 LangChain）。 具体工具的语义（做什么）在领域层定义； 工具的 LangChain 包装（, AI 工具端口（抽象基类）。      每一个领域工具需实现此接口，定义：     - name: LLM 用于识别的工具名称。     - descripti, 工具描述。LLM 阅读此文本决定何时调用工具。          建议包含：功能说明、适用场景、参数含义。, 执行工具逻辑。          Args:             **kwargs: LLM 传入的参数（字符串键值对），由具体工具自行解析和校验。, 工具注册表——全局 AITool 实例池。  启动时注册所有业务工具，运行时按名称解析，供 SkillAgentFactory 为每个 Skill 动态装配专属, 全局工具注册表。      以工具名称（AITool.name）为键存储所有可用工具实例。     SkillAgentFactory 根据 SkillConf (+3 more)

### Community 11 - "Domain Value Objects (Agent Identity, Skill)"
Cohesion: 0.13
Nodes (11): 装配该 Agent 的工具链。          若 prompt_config 使用了 skill_refs（动态模式），自动注入         ``Ski, 领域工具包——工具注册表、技能查询工具等。, 技能查询工具 —— 让 LLM 按需获取技能完整指令。  作为 Router Agent 的元工具，LLM 在选择技能后调用此工具获取 该技能的 task_in, 按名称查询技能详情。      在 Router Agent 中注册，让 LLM 先看菜单再获取完整指令。     避免把所有技能的详细 prompt 全部塞进, 初始化技能查询工具。          Args:             skill_repo: 技能配置仓储（含完整 SkillConfig）。, 查询技能详情。          Args:             **kwargs: 应包含 ``skill_name``（要查询的技能名）。, SkillLookupTool, BaseModel (+3 more)

### Community 12 - "Agent HTTP Router Interface"
Cohesion: 0.07
Nodes (25): EventSourceResponse, chat(), chat_stream(), Agent 对话路由 —— 流式（SSE）与非流式两端点。  接口层只翻译：ChatRequest → AgentRequest → 调 AgentServic, SSE 流式对话：逐 AgentStreamEvent 推送，ping=15s 保活。, ChatMessage, ChatRequest, ChatResponse (+17 more)

### Community 13 - "Skill Config & Agent Builder"
Cohesion: 0.20
Nodes (11): DeclarativeBase, 默认返回最近 size 条；size<=0 时返回全部。, Base, ConversationMessageRow, ConversationRow, 对话持久化的 SQLAlchemy 2.0 ORM 模型与建表助手。, async_sessionmaker, 对话仓储的 SQLAlchemy 实现 —— 显式映射，窗口加载 + 增量落库。 (+3 more)

### Community 14 - "Nacos Client Infrastructure"
Cohesion: 0.18
Nodes (7): NacosConfigService, NacosClient, Any, 获取 JSON 格式配置，解析为 dict。, 注册配置变更监听。          Nacos 上对应配置发生变化时，``callback`` 被调用并传入新的原始内容。          Args:, Nacos 配置中心客户端。      FastAPI 集成方式 —— 通过 lifespan 管理生命周期，通过 Depends 注入::, 建立 gRPC 连接，必须在 get/publish 之前调用。

### Community 15 - "SSE Encoder & HTTP Schemas"
Cohesion: 0.06
Nodes (32): P, Request, AgentIdentityRepository, AgentIdentity 配置仓储端口。  定义 Agent 身份定义配置的访问契约，由基础设施层 Nacos 适配器实现。, Agent 身份定义的配置仓储。      每个 key 对应一个 ``AgentIdentity`` 实例。, 获取指定 key 的 Agent 身份定义。          Args:             key: 配置键（如 ``"agent-identity"`, 注册 AgentIdentity 变更回调。          Args:             callback: 接收新的 AgentIdentity 实, ConfigRepository (+24 more)

### Community 16 - "Agent Service Test Support"
Cohesion: 0.12
Nodes (14): AgentResponse, AgentStreamEvent, BaseModel, Agent 数据传输对象（DTO）。  使用 Pydantic v2 定义 agent 调用的输入输出模型, 仅限 application 和 interfac, Agent 非流式响应。      Attributes:         reply: Agent 的最终回复文本。         thread_id: 关, Agent 流式事件。      支持六种事件类型：     - token: LLM 输出的增量文本片段。     - tool_start: 工具开始执行。, AgentResponseTest, AgentStreamEventTest (+6 more)

### Community 17 - "Skill Lookup & Tool Registry"
Cohesion: 0.14
Nodes (12): _build_classify_prompt(), LlmIntentRecognizer, Any, 基于 LLM 结构化输出的意图识别器 —— 实现 IntentRecognizer 端口。  单次 with_structured_output 调用，不是 R, 拼装分类 prompt：列技能目录 + 要求择一 + 允许 None。, 实现 IntentRecognizer 端口。, BuildPromptTest, _FakeLLM (+4 more)

### Community 18 - "LLM Config & Client Factory"
Cohesion: 0.16
Nodes (10): PostgresConfig, BaseModel, PostgreSQL 数据库连接配置。      支持通过环境变量 ``DATABASE_URL`` 覆盖连接字符串，同时提供连接池参数     的细粒度控制。, 获取完整的数据库连接 URL（与 db_dsn 等价，提供语义化别名）。, NacosPostgresConfigRepository, PostgreSQL 配置的 Nacos 仓储实现。  通过 Nacos 客户端拉取 ``postgres`` 配置项，解析为 ``PostgresConfig, PostgreSQL 数据库配置的 Nacos 仓储实现。      启动时从 Nacos 拉取数据库连接配置，并持续监听远程变更以热更新。     使用异步锁, 初始化仓储。          Args:             nacos_client: 已建立连接的 Nacos 客户端实例。 (+2 more)

### Community 19 - "Bootstrap Container Tests"
Cohesion: 0.20
Nodes (7): AgentRequest, Agent 调用请求。      Attributes:         messages: 对话消息列表，每条含 role 和 content。, AgentRequestTest, AgentServicePortTest, AgentService 端口的 runtime_checkable 校验测试。, runtime_checkable 后,结构性实现应通过 isinstance 检查。, _StubAgentService

### Community 20 - "End-to-End Integration Tests"
Cohesion: 0.21
Nodes (5): AgentRegistryTest, AgentRegistry 测试——get/available/catalog、缺失兜底、无兜底抛错。, _registry(), _skill(), _StubService

### Community 21 - "Routing Integration Tests"
Cohesion: 0.11
Nodes (9): _nacos_is_available(), NacosClient 单元测试。  需要 Docker 中运行 Nacos 才能通过集成测试。 若 Nacos 不可用，集成测试会自动跳过。, 检测本地 Nacos gRPC 端口 9848 是否可达。, NacosAgentIdentityRepository 集成测试。, NacosSkillConfigRepository 集成测试。, TestNacosAgentIdentityRepository, TestNacosClientLifecycle, TestNacosClientRead (+1 more)

### Community 22 - "Nacos Repository Implementation Tests"
Cohesion: 0.14
Nodes (7): ClientConfig, NacosConfig, BaseModel, 异常场景：未 start 就调用方法应抛出 RuntimeError。, TestNacosClientErrors, TestNacosClientNoServer, TestNacosConfig

### Community 23 - "Bootstrap App Factory Tests"
Cohesion: 0.13
Nodes (12): Container, BaseModel, 组合根产物:持有全部已装配依赖,构建后不可变。, 逆序释放全部资源(先数据库后 Nacos)。, NacosLLMConfigRepository, LLM 配置的 Nacos 适配器。      从 Nacos 读取 JSON 格式的 LLMConfig，缓存 + 热更新。, LoadedIdentityRepo, LoadedSkillRepo (+4 more)

### Community 25 - "LLM Intent Recognizer Tests"
Cohesion: 0.14
Nodes (8): create_conversation_tables(), AsyncEngine, 建对话相关表（MVP 用；生产改由 Alembic 迁移管理）。, _agent(), ConversationRepositoryTest, _make_repo(), async_sessionmaker, SqlAlchemyConversationRepository 测试——append-only、窗口、全量、唯一约束。

### Community 26 - "Tool Adapter Tests"
Cohesion: 0.06
Nodes (25): Exception, create_react_agent(), Any, ReAct Agent 工厂——基于 LangChain create_agent 组装 Agent。  LangChain 1.3.13 中 create_r, 创建 ReAct Agent。      使用 LangChain 的 create_agent API，底层基于 LangGraph StateGraph，, LLMClientFactory, Any, build_agent_registry() (+17 more)

### Community 27 - "Routing Policy Tests"
Cohesion: 0.19
Nodes (10): ConversationClosedError, 新建对话，生成 id，发 ConversationStarted。, AssistantResponded, ConversationClosed, ConversationStarted, 对话子域领域事件 —— 只表达「已发生的事实」。, _agent(), ConversationAggregateTest (+2 more)

### Community 28 - "Domain Prompts & General Skills"
Cohesion: 0.17
Nodes (5): AgentEntity, BaseModel, Agent 聚合根 —— AI 技能 Agent 的领域模型。  支持两种运行模式： - **单技能模式**：持有 SkillConfig + 业务工具，pro, AI 技能 Agent 聚合根。      职责：     - 持有 Agent 的身份标识和配置     - 管理工具链     - 对外暴露提示词渲染, AgentRouterTool

### Community 30 - "Database & Config Infrastructure"
Cohesion: 0.19
Nodes (8): Any, 技能子 Agent 工厂 —— 按 Skill 动态编译独立的 LangGraph Agent。  每个 Skill 拥有专属的 tools 列表和完整的系统, 按技能名获取或编译 Agent。          Args:             skill_name: 技能名称（对应 SkillConfig.name, 使缓存失效。          Args:             skill_name: 为 None 时清空全部缓存；否则仅清空指定技能的缓存。, 为每个 Skill 编译并缓存独立的 LangGraph Agent。      缓存的 agent 可直接执行，无需每次重建。当 SkillConfig 热更, 初始化工厂。          Args:             llm: LangChain BaseChatModel 实例（ChatOpenAI / C, 为一个 Skill 编译专属 LangGraph Agent。          解析 skill.tool_names → 从 ToolRegistry 获取, SkillAgentFactory

### Community 32 - "Agent Service Port Tests"
Cohesion: 0.17
Nodes (8): IntentRecognizer, Protocol, 意图识别端口 —— 输入对话 + 技能目录，输出结构化分类结果。, 识别当前对话最匹配的技能。基础设施层用 LLM 结构化输出实现。, 路由 Agent 服务 —— 实现 AgentService 端口，内敛路由复杂度。  编排：意图识别 → RoutingPolicy 裁决 → 分发到选中的技, 实现 AgentService 端口（run / stream）。, _routing_message(), RoutingAgentService

### Community 33 - "Test Support Fixtures"
Cohesion: 0.06
Nodes (27): AsyncExitStack, configure_logging(), create_app(), FastAPI, FastAPI 应用工厂与生命周期。  create_app() 创建应用:注册 lifespan 与 interfaces 层路由。 生产路径(contain, 幂等的全局日志配置(root 已有 handler 时 basicConfig 不生效)。, 创建 FastAPI 应用。      Args:         container: 预制容器(测试用),由调用方负责 shutdown;, 组合根:集中装配各层依赖。  build_container() 一次性完成全链装配(Nacos → 配置仓库 → 数据库 → Agent), 产出不可变 Co (+19 more)

### Community 34 - "Domain Event Tests"
Cohesion: 0.09
Nodes (12): datetime, Conversation 聚合根 —— 对话历史的唯一真相源。  以 Pydantic 模型 + PrivateAttr 承载封装的 append-only 集, DomainEvent, BaseModel, 领域事件基类 —— 聚合内产生的「已发生的事实」，跨模块解耦只经领域事件。, InMemoryEventPublisher, 进程内领域事件发布器 —— 实现 DomainEventPublisher 端口（MVP）。, 按事件类型分发给订阅者；handler 可同步或异步。 (+4 more)

### Community 35 - "Design Docs: Agent SSE Streaming"
Cohesion: 0.20
Nodes (11): Agent SSE 流式输出实现计划, HTTP 请求/响应 Schema (ChatRequest/ChatResponse/ChatMessage), 对话 (Conversation) 子域实现计划, Agent 动态路由与意图识别实现计划, AgentService 应用级单例 (lifespan 预热), AgentStreamEvent 六类事件 (token/tool_start/tool_end/done/error/routing), Agent SSE 流式输出设计, SSE 线上协议 (text/event-stream) (+3 more)

### Community 36 - "Design Docs: Conversation Aggregate"
Cohesion: 0.29
Nodes (11): InMemoryEventPublisher 进程内事件发布器, SqlAlchemyConversationRepository 仓储实现, 消息只追加不修改 (审计完整性), ContextWindowPolicy 上下文窗口策略, Conversation 聚合根, ConversationRepository 仓储端口 (domain ABC), 对话 (Conversation) 子域设计, DomainEventPublisher 端口 (application Protocol) (+3 more)

### Community 37 - "Nacos Client Infrastructure Tests"
Cohesion: 0.33
Nodes (7): AI 基础设施——LangChain ReAct Agent 的出站适配器实现。  包含： - agent_factory: 封装 create_agent 创, adapt_ai_tool(), adapt_ai_tools(), Any, 工具适配器——将领域层 AITool 端口适配为 LangChain Tool。  领域层定义工具的语义（做什么），基础设施层完成框架包装（怎么做）。 此模块负, 将单个领域 AITool 适配为 LangChain Tool。      生成一个异步 LangChain Tool，其输入为 JSON 字符串（键值对），, 批量将领域 AITool 列表适配为 LangChain Tool 列表。      Args:         tools: AITool 实例列表。

### Community 38 - "Project CLAUDE.md Conventions"
Cohesion: 0.22
Nodes (10): DDD 分层架构 (扁平布局), 依赖方向铁律: interfaces→application→domain←infrastructure, 域事件跨模块解耦 (进程内 message bus), Pydantic v2 优先, 禁止 dataclass, all_routers 汇总列表 (routes/__init__.py), app.state.container 单挂点设计, AsyncExitStack 资源生命周期管理, Bootstrap 组合根重构设计 (+2 more)

### Community 39 - "Design Docs: Intent Routing"
Cohesion: 0.33
Nodes (10): AgentRegistry 多技能注册表, GENERAL_SKILL 兜底通用技能, IntentClassification 值对象 (target_skill+confidence+reason), IntentRecognizer 意图识别端口, Agent 动态路由与意图识别设计, LlmIntentRecognizer 结构化输出实现, RoutingAgentService 路由分发编排, RoutingConfig 值对象 (置信度阈值+兜底技能名) (+2 more)

### Community 40 - "LLM Client Factory Infrastructure"
Cohesion: 0.24
Nodes (5): DatabaseManager, 释放所有引擎资源（异步 + 同步）并重置初始化状态。          通常在服务关闭时调用一次。, 数据库生命周期管理器。      封装异步/同步双引擎与会话工厂的创建、获取与销毁，从 Nacos 配置仓储     读取连接参数。初始化幂等，可安全用于 Fa, 初始化管理器。          Args:             config_repo: 已从 Nacos 加载配置的仓储实例。, 从 Nacos 配置创建引擎与会话工厂（幂等）。          仅首次调用生效；后续调用直接返回。          Raises:

### Community 42 - "Agent Router Tool Domain"
Cohesion: 0.22
Nodes (6): 更新提示词配置。          配置更新后，基础设施层需重新编译 agent。, AgentPromptConfig, BaseModel, Agent 提示词配置 —— 不可变值对象。  组合 AgentIdentity + SkillRef/SkillConfig + 运行时参数， 为一个 Age, Agent 的一整套提示词配置（不可变）。, 渲染完整系统提示词。          两种模式：         - **动态模式**（推荐）：若 ``skill_refs`` 非空，仅渲染技能菜单，

### Community 43 - "Database Config Infrastructure"
Cohesion: 0.25
Nodes (6): NacosConfigRepository, ABC, Nacos 配置仓储端口。  定义了从 Nacos 配置中心拉取配置、监听变更的抽象接口。 具体实现由各环境（本地文件、Nacos SDK）提供，通过依赖注入在, Nacos 配置仓储抽象基类。      负责从 Nacos 配置中心加载业务配置（如 LLM 参数、数据库连接信息等），     并监听远程配置变更以实现热更, 从 Nacos 拉取配置并写入本地缓存/配置对象。          具体实现应：         - 连接 Nacos 服务端，获取指定 data_id 与, Nacos 配置变更回调。          当 Nacos 服务端推送配置变更时，SDK 会调用此方法。         子类可覆写以在配置热更新后执行额外逻

### Community 45 - "Conversation Repository Implementation"
Cohesion: 0.25
Nodes (5): AsyncSession, Session, 获取一个新的异步会话。          调用方需自行管理会话生命周期（``await session.close()`` 或         使用 ``asy, 获取一个新的同步会话。          调用方需自行管理会话生命周期（``session.close()`` 或         使用 ``with`` 上下, 确保管理器已完成初始化，否则抛出明确错误。

### Community 46 - "Project Config, Docker & README"
Cohesion: 0.32
Nodes (8): 组合根 bootstrap (Container + build_container + create_app), build_container() async 全链装配, Container (frozen Pydantic 组合根), create_app() FastAPI 应用工厂, AI Finance 账票服务容器, Nacos 配置中心 (standalone), PostgreSQL 16 数据库, Bootstrap 组合根重构实施计划

### Community 47 - "Agent DTO & Application Services"
Cohesion: 0.25
Nodes (6): LLMFactory, Any, Protocol, LLM 工厂端口——定义创建 ChatModel 的抽象契约。  应用层依赖此端口，基础设施层对接具体 LLM provider（OpenAI、Anthropi, LLM 工厂抽象端口。      定义创建 LangChain BaseChatModel 实例的标准方法，     隐藏具体 provider 的配置细节。, 创建并返回 LangChain ChatModel 实例。          Args:             temperature: 温度参数，默认 0.

### Community 48 - "Conversation Event Publisher Infrastructure"
Cohesion: 0.29
Nodes (6): create_db_engine(), _mask_password(), AsyncEngine, 数据库管理器——管理 SQLAlchemy 异步/同步引擎与会话工厂。  基于 ``NacosPostgresConfigRepository`` 获取连接配置, 获取异步 SQLAlchemy 引擎（用于建表等直接引擎操作）。, 创建异步 SQLAlchemy 引擎（不需要 Nacos 配置的轻量入口）。      用于测试、本地开发等无需完整 Nacos 配置链的场景。     优先读

### Community 49 - "Design Docs: Bootstrap Composition Root"
Cohesion: 0.33
Nodes (7): AI Finance 账票服务, 稽核 (auditing) 业务模块, 账票 / billing 限界上下文, 收票 (receiving) 业务模块, 技术栈 (FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Alembic), Python 3.11 + uv 包管理器, 对话领域事件 (ConversationStarted/AssistantResponded/ConversationClosed)

### Community 51 - "Design Docs: Conversation Persistence"
Cohesion: 0.53
Nodes (6): AsyncPostgresSaver LangGraph 持久化 checkpointer, best-effort 落库策略 (失败仅告警不阻断对话), LangChain 对话持久化设计 (PostgreSQL), RecordingAgentService 持久化装饰器, 三张业务对话表 (conversation/turn/message), TokenUsage 值对象 (prompt/completion/total tokens)

### Community 52 - "LLM Client Factory Tests"
Cohesion: 0.31
Nodes (6): RoutingAgentService 测试——路由分发、routing 首帧、失败降级、run 回填。, RoutingAgentServiceTest, _service(), _skill(), _StubRecognizer, _StubWorker

### Community 57 - "Domain Prompts Value Objects"
Cohesion: 0.50
Nodes (3): Prompt, BaseModel, Prompt 值对象——系统提示词的领域建模。  Prompt 内容是领域知识（如"如何稽核发票"的业务规则）， 因此建模为不可变值对象，放在领域层。

### Community 58 - "Nacos Client Lifecycle Tests"
Cohesion: 0.21
Nodes (6): 路由端到端集成——首帧 routing、兜底、分类器故障降级仍 200。, _routing_service(), RoutingIntegrationTest, _stream_events(), _StubRecognizer, _StubWorker

### Community 88 - "uuid7"
Cohesion: 0.17
Nodes (6): 生成新标识——单调 uuid7，ID 字典序即创建时间序。, 进程内单调 UUIDv7 生成器（RFC 9562, Method 1）。  纯标准库实现，零第三方依赖——供各子域生成趋势递增的聚合标识。 单调性：同进程严格, uuid7(), IdGeneratorTest, 单调 uuid7 生成器测试——格式、位段、严格递增、并发唯一、回拨不倒退。, UUID

### Community 89 - "InterfacesApiTest"
Cohesion: 0.29
Nodes (5): InterfacesApiTest, _make_app(), FastAPI, interfaces/api 路由与 DI provider 测试——手搭最小 app + 鸭子类型桩容器。, _StubSkillRepo

### Community 90 - "会话唯一 ID 设计：进程内单调 UUIDv7"
Cohesion: 0.17
Nodes (11): 1. ID 生成器 `src/domain/shared/id_generator.py`（新增）, 2. `ConversationId` 值对象加固 `src/domain/conversation/value_objects.py`, 3. 聚合工厂 `src/domain/conversation/aggregate.py`, 4. 接口层格式校验 `src/interfaces/conversation/schemas.py`, 会话唯一 ID 设计：进程内单调 UUIDv7, 存储与兼容, 影响面清单, 方案总览 (+3 more)

### Community 93 - "ConversationRepository"
Cohesion: 0.22
Nodes (5): ConversationRepository, ABC, 对话仓储端口（domain）。聊天闭环用窗口加载 + 增量落库；审计走全量。, 加载对话头 + 最近 window 条消息（None 表示全量）。, upsert 对话头 + 只 INSERT pull_new_messages() 的新消息，不重写历史。

### Community 94 - "DispatchToSkillTool"
Cohesion: 0.20
Nodes (8): DispatchToSkillTool, _extract_last_ai_content(), Any, 技能分派工具 —— 将用户任务转发给指定 Skill 的专属子 Agent 执行。  作为 Router Agent 的执行工具，LLM 在查询技能详情后调用此, 从 LangGraph 消息列表中提取最后一条 AI 消息的文本内容。, 将任务转发给指定技能的专属子 Agent 执行。      子 Agent 持有该技能专属的 tools 和完整 prompt，Router Agent, 初始化分派工具。          Args:             agent_factory: 子 Agent 工厂（负责编译和缓存）。, 执行技能任务。          Args:             **kwargs: 应包含 ``skill_name``（技能名）和 ``task``（任

### Community 95 - "Global Constraints"
Cohesion: 0.25
Nodes (7): Global Constraints, Task 1: 单调 uuid7 生成器, Task 2: ConversationId 加固（pattern 校验 + new() 工厂）, Task 3: 聚合工厂切换到单调 ID, Task 4: 接口层入参格式校验（非法 conversation_id 直接 422）, 会话单调 UUIDv7 ID 实施计划, 收尾核对（Task 4 之后）

## Knowledge Gaps
- **57 isolated node(s):** `ai-finance`, `ai-finance`, `Task 1: 单调 uuid7 生成器`, `Task 2: ConversationId 加固（pattern 校验 + new() 工厂）`, `Task 3: 聚合工厂切换到单调 ID` (+52 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **27 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Container` connect `Bootstrap App Factory Tests` to `Intent Routing & Agent Registry`, `Test Support Fixtures`, `Agent Service Port Tests`, `Agent Entity, DTO & Service Ports`, `Agent Config API Routes`, `Conversation REST Router & Schemas`, `Nacos Config Repository Ports`, `LLM Client Factory Infrastructure`, `Domain Shared AI Tools`, `Nacos Client Infrastructure`, `Skill Lookup & Tool Registry`, `LLM Config & Client Factory`, `Nacos Repository Implementation Tests`, `Tool Adapter Tests`?**
  _High betweenness centrality (0.181) - this node is a cross-community bridge._
- **Why does `AgentRequest` connect `Bootstrap Container Tests` to `Agent Service Port Tests`, `Conversation Use Case & Persistence`, `Test Support Fixtures`, `HTTP SSE Streaming & Agent Router`, `Agent Config API Routes`, `Conversation REST Router & Schemas`, `Conversation Value Objects`, `Agent HTTP Router Interface`, `Agent Service Test Support`, `End-to-End Integration Tests`, `LLM Client Factory Tests`, `Bootstrap App Factory Tests`, `Nacos Client Lifecycle Tests`?**
  _High betweenness centrality (0.116) - this node is a cross-community bridge._
- **Why does `AgentId` connect `Conversation Use Case & Persistence` to `Agent Entity, DTO & Service Ports`, `Conversation Value Objects`, `Domain Shared AI Tools`, `Domain Value Objects (Agent Identity, Skill)`, `Agent Router Tool Domain`, `Skill Config & Agent Builder`, `LLM Intent Recognizer Tests`, `Routing Policy Tests`, `Domain Prompts & General Skills`?**
  _High betweenness centrality (0.109) - this node is a cross-community bridge._
- **Are the 43 inferred relationships involving `AgentRequest` (e.g. with `SendMessageUseCase` and `.execute()`) actually correct?**
  _`AgentRequest` has 43 INFERRED edges - model-reasoned connections that need verification._
- **Are the 29 inferred relationships involving `SkillConfig` (e.g. with `IntentRecognizer` and `AgentRegistry`) actually correct?**
  _`SkillConfig` has 29 INFERRED edges - model-reasoned connections that need verification._
- **Are the 33 inferred relationships involving `AgentResponse` (e.g. with `AgentService` and `RoutingAgentService`) actually correct?**
  _`AgentResponse` has 33 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `IntentClassification` (e.g. with `IntentRecognizer` and `RoutingPolicy`) actually correct?**
  _`IntentClassification` has 25 INFERRED edges - model-reasoned connections that need verification._