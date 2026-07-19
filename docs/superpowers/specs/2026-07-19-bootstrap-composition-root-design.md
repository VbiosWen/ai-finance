# Bootstrap 组合根重构设计（启动链 + 依赖注入归位）

| 项 | 内容 |
|---|---|
| 日期 | 2026-07-19 |
| 状态 | 已评审 · 待实现 |
| 范围 | `main.py` / `bootstrap` 启动链与 FastAPI 依赖注入的整体重构；不实现业务 feature |
| 相关分支 | `feature/ddd-ai-finance` |
| 相关设计 | [Agent SSE 流式输出设计](2026-07-19-agent-sse-streaming-design.md) · [Agent 动态路由与意图识别设计](2026-07-19-intent-routing-design.md) · [LangChain 对话持久化设计](2026-07-19-conversation-persistence-design.md) |

---

## 1. 背景与现状

当前启动链与 DI 存在五个问题（按严重程度排序）：

| # | 问题 | 位置 | 后果 |
|---|---|---|---|
| 1 | `get_container` **每个 HTTP 请求重建整个容器** | [`bootstrap/dependencies.py:63`](../../../src/bootstrap/dependencies.py) | 每请求新建 LLM 客户端、Agent、`MemorySaver`（多轮记忆失效）、DB 引擎（连接池泄漏）。[SSE 设计 §8](2026-07-19-agent-sse-streaming-design.md) 已把「agent_service 单例化」列为目标 |
| 2 | **API 路由写在 bootstrap** | [`bootstrap/main.py:106-132`](../../../src/bootstrap/main.py) | 违反分层：路由属 interfaces 层；bootstrap 应只装配与启动 |
| 3 | **FastAPI `Depends` 胶水放在 bootstrap** | `bootstrap/dependencies.py` | CLAUDE.md 把「依赖注入（入站适配器）」划给 interfaces 层 |
| 4 | **无 `create_app()` 工厂**；装配逻辑割裂为两套 | `bootstrap/main.py`（lifespan → `app.state`）与 `bootstrap/container.py`（`build_container` → `Container`） | app 在模块导入时创建；同一批依赖两条装配路径、两种取用方式 |
| 5 | `Container` 用 `@dataclass` | [`bootstrap/container.py:29`](../../../src/bootstrap/container.py) | 违反项目「Pydantic v2 优先、禁止 dataclass」规范 |

另有安全问题：`GET /config/{data_id}` 可读取任意 Nacos 配置原文（包括数据库密码所在配置），**决定直接移除**（调试需求由 Nacos 控制台满足）。

**背景约束**：三份「已评审 · 待实现」设计（SSE 流式、意图路由、对话持久化）全部要挂在 bootstrap 上——Agent 注册表、`RoutingAgentService`、`RecordingAgentService`、`AsyncPostgresSaver`、`DatabaseManager` 均需启动时一次性装配。本次重构是这三个 feature 的地基。

## 2. 目标与非目标

### 目标

- **装配单一出口**：全部依赖在 `build_container()`（async）内一次性装配，lifespan 仅负责「启动时调用、挂载、关闭」。
- **agent_service 应用级单例**：随容器一次装配，`thread_id` 多轮记忆跨请求生效（落实 SSE 设计 §8）。
- **路由与 DI 胶水归位 interfaces 层**；DI provider 签名只暴露 domain / application 端口类型。
- **`create_app()` 工厂**：支持测试注入预制容器与 uvicorn factory 模式。
- `Container` 转 **Pydantic v2**，消除 dataclass 违规。
- 移除 `GET /config/{data_id}`；其余现有路由（`/health`、`/agent/identity`、`/agent/skills`）**行为不变**。

### 非目标

- **不实现**三份 feature 设计中的任何业务组件（SSE 端点、意图路由、对话落库、`AsyncPostgresSaver`）——只保证它们的装配点就绪。
- 不做配置热更 → Agent 重建（[意图路由设计 §390](2026-07-19-intent-routing-design.md)：MVP 启动装配一次，热重建为后续增强；配置仓库自身的热更能力不受影响）。
- 不修正 `LangChainAgentService` 误置于 `interfaces/ai/` 的旧账（三份设计均记为遗留项，保持一致）。
- 不新增响应 schema / 全局异常处理器（现有路由维持 `model_dump()` 返回）。

## 3. 关键设计决策

| 决策 | 选择 | 理由 | 被否方案 |
|---|---|---|---|
| 组合结构 | **统一 Container 组合根**，`app.state.container` 单挂点 | 装配单出口；feature 落地只改 `build_container` + 加 provider；测试整体替换容器即可 | app.state 平铺（装配散落 lifespan、无类型聚合、逐属性塞桩）；第三方 DI 框架（引依赖、与 `Depends` 双轨，YAGNI） |
| 装配时机 | **lifespan 内 async 装配** | Nacos gRPC / DB 初始化是 async，必须与 uvicorn 同一事件循环；`main()` 里先 `asyncio.run` 再起 uvicorn 会跨两个 loop，gRPC 客户端绑 loop 会坏 | 启动前同步装配（跨 loop 隐患）；每请求装配（现状缺陷） |
| 资源生命周期 | **`contextlib.AsyncExitStack`** | 装配失败自动逆序回收半成品；成功后所有权移交 `Container.shutdown()`；feature 新增资源只需注册进 stack，关闭顺序自动正确 | 手写 try/except + 逐资源关闭（顺序靠人维护，易漏） |
| DI 分层 | provider **函数体**读 `app.state.container`（无类型，不构成 import 依赖），**签名**只标端口类型 | interfaces 只 import domain / application，依赖方向铁律达成 | provider 标注 infrastructure 具体类型（现状，interfaces 泄漏基础设施）；为取容器让 interfaces import bootstrap（形成环） |
| Container 字段类型 | `agent_service` 标 **application 端口 `AgentService`**（Protocol 加 `@runtime_checkable`） | 为 `RoutingAgentService` / `RecordingAgentService` 装饰器替换留位，装配处换实现零改动 | 标具体类 `LangChainAgentService`（装饰器替换时要改字段类型） |
| Container 建模 | **Pydantic v2**，`frozen=True` + `arbitrary_types_allowed` | 符合项目规范；构建完成后不可篡改 | dataclass（违规）；普通类（丢校验） |
| 测试开关 | **删除 `skip_ai` / `skip_db`** | 测试用桩对象直接构造 `Container`，不再需要生产代码里的测试旁路 | 保留开关（生产代码为测试留后门） |
| `/config/{data_id}` | **移除** | 可读任意配置原文（含 DB 密码），生产风险大 | 保留加白名单/环境开关（仍有维护面；调试可走 Nacos 控制台） |

## 4. 目标文件布局

```
main.py                          # 根启动器，不变（sys.path + 委托 bootstrap.main:main）
src/bootstrap/
  container.py                   # Container（Pydantic）+ build_container()（async 全链装配）
  app.py                         # 新增：create_app() 工厂 + lifespan + configure_logging()
  main.py                        # 瘦身：main() 只调 uvicorn
  dependencies.py                # ❌ 删除（职责移至 interfaces/api/dependencies.py）
src/interfaces/api/
  __init__.py
  dependencies.py                # 新增：DI provider，签名只标端口类型
  routes/
    __init__.py                  # all_routers 列表，供 create_app 统一 include
    health.py                    # GET /health
    agent_config.py              # GET /agent/identity、GET /agent/skills
```

## 5. Container 与 build_container

### 5.1 Container（Pydantic v2）

```python
class Container(BaseModel):
    """组合根产物：持有全部已装配依赖，构建后不可变。"""

    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    # 基础设施
    nacos_client: NacosClient
    postgres_config_repo: NacosPostgresConfigRepository
    db_manager: DatabaseManager

    # 配置仓库（预热完成）
    agent_identity_repo: NacosAgentIdentityRepository
    skill_config_repo: NacosSkillConfigRepository
    llm_config_repo: NacosLLMConfigRepository

    # AI
    llm_factory: LLMClientFactory
    tools: list[AITool]
    agent_service: AgentService          # application 端口，装饰器替换零改动

    # 资源关闭栈（repr 排除）
    exit_stack: AsyncExitStack

    async def shutdown(self) -> None:
        """逆序释放全部资源（先 DB 后 Nacos）。"""
        await self.exit_stack.aclose()
```

配套小改：`application/ports/agent_service.py` 的 `AgentService` Protocol 加 `@runtime_checkable`（Pydantic `arbitrary_types_allowed` 校验走 `isinstance`，非 runtime_checkable 的 Protocol 会直接 `TypeError`）。

### 5.2 build_container 装配时序

```python
async def build_container() -> Container:
```

1. `NacosClient.start()`（地址/命名空间读环境变量 `NACOS_ADDRESS` / `NACOS_NAMESPACE`，现状不变）→ 注册 `stop()` 进 stack
2. `NacosPostgresConfigRepository.load()` → `DatabaseManager.initialize()` → 注册 `dispose()` 进 stack
3. `agent_identity_repo.load()`、`skill_config_repo.load()`、`llm_config_repo.load()` 预热
4. `LLMClientFactory(llm_config_repo.get())` → `adapt_ai_tools` → `create_react_agent`（仍用 `DEFAULT_AGENT_PROMPT` 单 Agent）→ `LangChainAgentService`
5. 构造并返回 `Container`（stack 所有权移交容器）

**失败语义**：任一步抛错 → `AsyncExitStack` 逆序回收已启动资源 → 异常上抛 → lifespan 失败 → uvicorn 退出（fail-fast，不带病运行）。

原 `create_db_engine` 独立引擎路径并入 `DatabaseManager`（lifespan 现状已用后者，`db_engine` 字段与 `db_url` 参数随 `skip_*` 开关一并删除）。

## 6. 启动链

```
根 main.py → bootstrap.main:main() → uvicorn.run("bootstrap.app:create_app", factory=True)
                                          └→ create_app() → FastAPI(lifespan) + include all_routers
                                                lifespan 启动：container = await build_container()
                                                              app.state.container = container
                                                lifespan 关闭：await container.shutdown()
```

- `create_app(container: Container | None = None) -> FastAPI`：**测试**传入预制容器，lifespan 跳过装配直接挂载；**生产**不传，lifespan 内装配。落实 CLAUDE.md 的 `create_app(container)` 措辞。
- uvicorn factory 模式（字符串引用 + `factory=True`）支持 `--reload` / 多 worker。
- `host` / `port` 读环境变量 `HOST` / `PORT`，默认 `0.0.0.0:8000`。
- `configure_logging()`：幂等的 `basicConfig` 封装，`create_app()` 开头调用（从 lifespan 移出）。

## 7. interfaces 层：DI 与路由

### 7.1 dependencies.py

```python
def get_agent_identity_repo(request: Request) -> AgentIdentityRepository:   # domain 端口
    return request.app.state.container.agent_identity_repo

def get_skill_config_repo(request: Request) -> SkillConfigRepository:       # domain 端口
    return request.app.state.container.skill_config_repo

def get_agent_service(request: Request) -> AgentService:                    # application 端口
    return request.app.state.container.agent_service                        # SSE plan 备用
```

- 函数体经 `app.state`（`Any`）取容器字段，**不产生对 bootstrap / infrastructure 的 import**；签名只标 domain / application 端口。
- 原 `get_nacos_client` / `get_db_manager` / `get_postgres_config_repo` / `get_llm_config_repo` **删除**：现存路由用不到；后续 feature 需要时按端口类型再加。

### 7.2 routes

| 路由 | 去向 | 行为 |
|---|---|---|
| `GET /health` | `routes/health.py` | 不变 |
| `GET /agent/identity` | `routes/agent_config.py` | 不变（`repo.get("agent-identity").model_dump()`） |
| `GET /agent/skills` | `routes/agent_config.py` | 不变 |
| `GET /config/{data_id}` | — | **移除**（安全） |

`routes/__init__.py` 导出 `all_routers: list[APIRouter]`，`create_app()` 统一 `include_router`。

## 8. 测试策略

| 测试 | 做法 |
|---|---|
| 新增 `tests/test_bootstrap_app.py` | 桩对象构造 `Container` → `create_app(container)` → `TestClient` 验证 `/health`、`/agent/identity`、`/agent/skills` 与 `/config/{data_id}` 404 |
| 原 `test_smoke` 的 `build_container(skip_ai=True)` 用例 | 改为「桩对象直接构造 Container」的构造测试 |
| `build_container` 全链 | 需真实 Nacos + DB，**不进单测**（后续如需，另立集成测试并按环境跳过） |
| 冒烟 | `uv run python -c "from bootstrap.app import create_app; create_app()"`（不触发 lifespan，验证 import 图与路由注册） |

## 9. 与三份待实现设计的衔接

| 设计 | 原落点 | 新落点 |
|---|---|---|
| [SSE](2026-07-19-agent-sse-streaming-design.md)：agent_service 单例化（§8） | 自带任务 | **本重构直接完成**；plan 执行时跳过该项，chat 路由落 `interfaces/api/routes/`，`get_agent_service` 已备好 |
| [持久化](2026-07-19-conversation-persistence-design.md)：saver / DatabaseManager 装配 | lifespan + `app.state` | `build_container` 内 + ExitStack 注册 dispose |
| [意图路由](2026-07-19-intent-routing-design.md)：注册表构建 | `build_container` | 位置不变，替换 §5.2 第 4 步的单 Agent 装配 |

**注记**:三份 plan 中引用 `bootstrap/main.py` 路由、`bootstrap/dependencies.py`、`app.state.<单项依赖>` 的任务，执行时以本设计的新路径为准（`app.state.container.<字段>` / `interfaces/api/`）。

## 10. CLAUDE.md 修订

「组合根 bootstrap」一节同步为：`build_container()` 为 async 单一装配出口；`bootstrap/app.py` 提供 `create_app(container=None)` 工厂；异步装配因事件循环约束置于 lifespan 内；FastAPI 的 DI 胶水位于 `interfaces/api/dependencies.py`。

## 11. 遗留项

- `LangChainAgentService` 位于 `interfaces/ai/`（应属 infrastructure）——与三份设计口径一致，另行处理。
- 配置热更 → Agent/注册表原子重建：意图路由 feature 的后续增强。
- `/agent/*` 配置路由的响应 schema 化：待 SSE plan 引入 schema 目录时顺带。
