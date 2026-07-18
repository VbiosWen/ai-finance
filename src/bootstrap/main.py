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
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from bootstrap.dependencies import (
    get_agent_identity_repo,
    get_container,
    get_nacos_client,
    get_skill_config_repo,
)
from infrastructure.client.nacos import NacosClient, NacosConfig
from infrastructure.ports import (
    NacosAgentIdentityRepository,
    NacosSkillConfigRepository,
)

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
        address="127.0.0.1:8848",
        namespace="ai-finance",
    )
    client = NacosClient(cfg)
    await client.start()
    app.state.nacos_client = client
    logger.info("Nacos 客户端已启动")

    # 预热：启动时加载配置仓库，避免首个请求等待
    from infrastructure.ports import (
        NacosAgentIdentityRepository,
        NacosSkillConfigRepository,
    )

    agent_repo = NacosAgentIdentityRepository(client)
    await agent_repo.load()
    app.state.agent_identity_repo = agent_repo
    logger.info("AgentIdentity 配置已预热")

    skill_repo = NacosSkillConfigRepository(client)
    await skill_repo.load()
    app.state.skill_config_repo = skill_repo
    logger.info("SkillConfig 配置已预热")

    yield

    await client.stop()
    logger.info("Nacos 客户端已关闭")


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
