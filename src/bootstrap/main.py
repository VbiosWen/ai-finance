"""FastAPI 服务启动入口。

职责：
- 创建 FastAPI app
- lifespan 管理 Nacos 客户端生命周期
- 注册路由
- 启动 uvicorn

依赖注入函数统一在 ``bootstrap.dependencies`` 中定义。
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from bootstrap.dependencies import (
    get_agent_identity_repo,
    get_llm_config_repo,
    get_nacos_client,
    get_skill_config_repo,
)
from infrastructure.client.database import DatabaseManager
from infrastructure.client.nacos import NacosClient, NacosConfig
from infrastructure.ports import (
    NacosAgentIdentityRepository,
    NacosSkillConfigRepository,
)
from infrastructure.ports.data_base_config_nacos_repository import NacosPostgresConfigRepository
from infrastructure.ports.nacos_llm_config_repository import NacosLLMConfigRepository

logger = logging.getLogger("ai-finance")


# ---------------------------------------------------------------------------
# Lifespan —— Nacos gRPC 连接的 start / stop
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    cfg = NacosConfig(
        address=os.getenv("NACOS_ADDRESS", "127.0.0.1:8848"),
        namespace=os.getenv("NACOS_NAMESPACE", "ai-finance"),
    )
    client = NacosClient(cfg)
    await client.start()
    app.state.nacos_client = client

    # ── 数据库配置 + 管理器 ──────────────────────────────────────
    postgres_repo = NacosPostgresConfigRepository(client)
    await postgres_repo.load()
    app.state.postgres_config_repo = postgres_repo

    db_manager = DatabaseManager(postgres_repo)
    await db_manager.initialize()
    app.state.db_manager = db_manager
    logger.info("数据库管理器已就绪")

    # ── 其他配置仓库预热 ─────────────────────────────────────────
    agent_repo = NacosAgentIdentityRepository(client)
    await agent_repo.load()
    app.state.agent_identity_repo = agent_repo
    logger.info("AgentIdentity 配置已预热")

    skill_repo = NacosSkillConfigRepository(client)
    await skill_repo.load()
    app.state.skill_config_repo = skill_repo
    logger.info("SkillConfig 配置已预热")

    llm_repo = NacosLLMConfigRepository(client)
    await llm_repo.load()
    app.state.llm_config_repo = llm_repo
    logger.info("LLMConfig 配置已预热")

    yield

    # ── 优雅关闭：先释放数据库连接池，再停 Nacos 客户端 ─────────
    await db_manager.dispose()
    await client.stop()


# ---------------------------------------------------------------------------
# FastAPI 应用
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Finance 账票服务",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# 路由
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/agent/identity")
async def agent_identity(
    repo: NacosAgentIdentityRepository = Depends(get_agent_identity_repo),
) -> dict:
    return repo.get("agent-identity").model_dump()


@app.get("/agent/skills")
async def agent_skills(
    repo: NacosSkillConfigRepository = Depends(get_skill_config_repo),
) -> list[dict]:
    return [s.model_dump() for s in repo.get("skill-configs")]


@app.get("/config/{data_id}")
async def read_config(
    data_id: str,
    group: str = "AI_FINANCE",
    client: NacosClient = Depends(get_nacos_client),
) -> dict[str, str | None]:
    content = await client.get_config(data_id, group=group)
    return {"data_id": data_id, "group": group, "content": content}


# ---------------------------------------------------------------------------
# 启动入口
# ---------------------------------------------------------------------------


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
