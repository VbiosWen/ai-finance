"""PostgreSQL 配置的 Nacos 仓储实现。

通过 Nacos 客户端拉取 ``postgres`` 配置项，解析为 ``PostgresConfig``，
并注册 watcher 实现配置热更新。
"""

import asyncio
from logging import getLogger

import yaml

from infrastructure.client.nacos import NacosClient
from infrastructure.config.database_config import PostgresConfig
from infrastructure.ports.nacos_config_repository import NacosConfigRepository

logger = getLogger(__name__)


class PostgresConfigRepository(NacosConfigRepository):
    """PostgreSQL 数据库配置的 Nacos 仓储实现。

    启动时从 Nacos 拉取数据库连接配置，并持续监听远程变更以热更新。
    使用异步锁保证并发安全，仅加载一次。

    Attributes:
        _data_id: Nacos 中该配置的 data_id（固定为 ``"postgres"``）。
        _group: Nacos 中该配置的 group（固定为 ``"AI-FINANCE"``）。
    """

    def __init__(self, nacos_client: NacosClient) -> None:
        """初始化仓储。

        Args:
            nacos_client: 已建立连接的 Nacos 客户端实例。
        """
        self._database_config: PostgresConfig | None = None
        """当前生效的数据库配置，首次加载前为 None。"""
        self._load_lock = asyncio.Lock()
        """异步锁，防止并发重复加载。"""
        self._data_id: str = "postgres"
        """Nacos data_id。"""
        self._group: str = "AI-FINANCE"
        """Nacos group。"""
        self._loaded: bool = False
        """是否已完成首次加载的标记。"""
        self._client = nacos_client
        """Nacos 客户端引用。"""

    # ── 生命周期 ──────────────────────────────────────────────────────────

    async def load(self) -> None:
        """从 Nacos 拉取数据库配置并注册变更监听。

        仅首次调用生效（幂等），后续调用直接返回。
        加载成功后将 ``_database_config`` 置为解析后的配置对象，
        并通过 ``add_watcher`` 注册 ``_on_config_changed`` 回调。
        """
        async with self._load_lock:
            if self._loaded:
                return

            raw = await self._client.get_config(self._data_id, self._group)
            if raw:
                self._database_config = PostgresConfig(**yaml.safe_load(raw))
                logger.info("已加载数据库配置（Nacos）。")
            else:
                logger.warning(
                    "Nacos 中未找到数据库配置: data_id=%s, group=%s",
                    self._data_id,
                    self._group,
                )

            # 注册配置变更监听，实现热更新
            await self._client.add_watcher(
                self._data_id,
                self._group,
                self._on_config_changed,
            )

    # ── 回调 ──────────────────────────────────────────────────────────────

    def _on_config_changed(self, raw: str) -> None:
        """Nacos 配置变更回调——热更新数据库配置。

        当 Nacos 服务端推送配置变更时自动触发，解析原始内容并替换
        ``_database_config``。

        Args:
            raw: Nacos 推送的原始配置内容（YAML 字符串）。
        """
        try:
            parsed = yaml.safe_load(raw)
            self._database_config = PostgresConfig(**parsed)
            logger.info("数据库配置已热更新（Nacos）。")
        except Exception:
            logger.exception("数据库配置热更新失败，将继续使用旧配置。")

