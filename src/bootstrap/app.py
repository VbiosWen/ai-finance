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
from interfaces.http.agent_router import router as agent_router

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
    app.include_router(agent_router)
    return app
