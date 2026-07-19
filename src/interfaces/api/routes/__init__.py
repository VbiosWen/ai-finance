"""路由汇总——create_app 统一 include。"""
from fastapi import APIRouter

from interfaces.api.routes.agent_config import router as agent_config_router
from interfaces.api.routes.health import router as health_router

all_routers: list[APIRouter] = [health_router, agent_config_router]

__all__ = ["all_routers"]
