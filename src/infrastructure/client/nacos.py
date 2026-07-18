from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable

from pydantic import BaseModel, Field
from v2.nacos import (
    ClientConfig,
    ClientConfigBuilder,
    ConfigParam,
    GRPCConfig,
    NacosConfigService,
)

logger = logging.getLogger("ai-finance")


class NacosConfig(BaseModel):
    """Nacos 连接配置。"""

    address: str = Field(default="127.0.0.1:8848", description="连接地址 url:port")
    namespace: str = Field(default="", description="命名空间")

    model_config = {"frozen": True}

    def get_client_config(self) -> ClientConfig:
        return (
            ClientConfigBuilder()
            .server_address(self.address)
            .namespace_id(self.namespace)
            .log_level(logging.INFO)
            .grpc_config(GRPCConfig(grpc_timeout=10_000))
            .build()
        )


class NacosClient:
    """Nacos 配置中心客户端。

    FastAPI 集成方式 —— 通过 lifespan 管理生命周期，通过 Depends 注入::

        # main.py
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            client = NacosClient(NacosConfig())
            await client.start()
            app.state.nacos_client = client
            yield
            await client.stop()

        # routes.py
        async def get_nacos(request: Request) -> NacosClient:
            return request.app.state.nacos_client

        @router.get("/config")
        async def get_config(client: NacosClient = Depends(get_nacos)):
            return await client.get_config("llm-config", group="AI_FINANCE")
    """

    def __init__(self, nacos_config: NacosConfig) -> None:
        self._nacos_config = nacos_config
        self._client_config = nacos_config.get_client_config()
        self._nacos_service: NacosConfigService | None = None

    # ── 生命周期 ──────────────────────────────────────────

    async def start(self) -> None:
        """建立 gRPC 连接，必须在 get/publish 之前调用。"""
        if self._nacos_service is not None:
            return
        self._nacos_service = await NacosConfigService.create_config_service(
            self._client_config
        )
        logger.info("Nacos 客户端已启动")

    async def stop(self) -> None:
        """释放 gRPC 连接。"""
        if self._nacos_service is not None:
            await self._nacos_service.shutdown()
            self._nacos_service = None
            logger.info("Nacos 客户端已关闭")

    async def __aenter__(self) -> "NacosClient":
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

    def _ensure_started(self) -> NacosConfigService:
        if self._nacos_service is None:
            raise RuntimeError("Nacos 客户端未启动，请先调用 start()")
        return self._nacos_service

    # ── 配置操作 ──────────────────────────────────────────

    async def get_config(self, data_id: str, group: str) -> str | None:
        """获取配置原始内容。"""
        svc = self._ensure_started()
        param = ConfigParam(data_id=data_id, group=group)
        content = await svc.get_config(param)
        return content if content else None

    async def get_json(self, data_id: str, group: str) -> dict[str, Any]:
        """获取 JSON 格式配置，解析为 dict。"""
        raw = await self.get_config(data_id, group)
        if not raw:
            return {}
        return json.loads(raw)

    # ── 配置监听（热更新）──────────────────────────────────

    async def add_watcher(
        self,
        data_id: str,
        group: str,
        callback: Callable[[str], None],
    ) -> None:
        """注册配置变更监听。

        Nacos 上对应配置发生变化时，``callback`` 被调用并传入新的原始内容。

        Args:
            data_id: 配置 dataId。
            group: 配置分组。
            callback: 签名为 ``(raw_content: str) -> None`` 的回调。
        """
        svc = self._ensure_started()

        def _listener(config_dict: dict[str, str]) -> None:
            content = config_dict.get("content", "")
            logger.info("Nacos 配置变更: data_id=%s group=%s", data_id, group)
            try:
                callback(content)
            except Exception:
                logger.exception("Nacos watcher 回调异常: data_id=%s", data_id)

        await svc.add_listener(data_id, group, _listener)
        logger.info("已注册 Nacos watcher: data_id=%s group=%s", data_id, group)

    async def remove_watcher(
        self,
        data_id: str,
        group: str,
        callback: Callable[[str], None],
    ) -> None:
        """移除配置变更监听。"""
        svc = self._ensure_started()
        await svc.remove_listener(data_id, group, callback)
        logger.info("已移除 Nacos watcher: data_id=%s group=%s", data_id, group)

