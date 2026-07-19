"""数据库管理器——管理 SQLAlchemy 异步/同步引擎与会话工厂。

基于 ``NacosPostgresConfigRepository`` 获取连接配置，提供异步（asyncpg）与同步
（psycopg2）双引擎，并通过异步锁保证线程安全的单次初始化。
"""

from __future__ import annotations

import asyncio
from logging import getLogger

from sqlalchemy import Engine, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import Session, sessionmaker

from infrastructure.ports.data_base_config_nacos_repository import (
    NacosPostgresConfigRepository,
)

logger = getLogger(__name__)


class DatabaseManager:
    """数据库生命周期管理器。

    封装异步/同步双引擎与会话工厂的创建、获取与销毁，从 Nacos 配置仓储
    读取连接参数。初始化幂等，可安全用于 FastAPI lifespan 中。

    使用方式::

        manager = DatabaseManager(config_repo)
        await manager.initialize()

        async with manager.async_session() as session:
            ...

        with manager.sync_session() as session:
            ...

        await manager.dispose()
    """

    def __init__(self, config_repo: NacosPostgresConfigRepository) -> None:
        """初始化管理器。

        Args:
            config_repo: 已从 Nacos 加载配置的仓储实例。
        """
        self._config_repo = config_repo

        self._async_engine: AsyncEngine | None = None
        self._async_sessionmaker: async_sessionmaker[AsyncSession] | None = None

        self._sync_engine: Engine | None = None
        self._sync_sessionmaker: sessionmaker[Session] | None = None

        self._initialized: bool = False
        self._init_lock = asyncio.Lock()

    # ── 初始化 ──────────────────────────────────────────────────────────

    async def initialize(self) -> None:
        """从 Nacos 配置创建引擎与会话工厂（幂等）。

        仅首次调用生效；后续调用直接返回。

        Raises:
            RuntimeError: 配置尚未从 Nacos 加载（``get_config()`` 返回 None）。
        """
        async with self._init_lock:
            if self._initialized:
                return

            config = self._config_repo.get_config()
            if config is None:
                raise RuntimeError(
                    "数据库配置未就绪，请先调用 NacosPostgresConfigRepository.load()"
                )

            # ── 异步引擎（asyncpg 驱动）────────────────────────────────
            self._async_engine = create_async_engine(
                config.url,
                pool_size=config.pool_size,
                max_overflow=config.max_overflow,
                pool_recycle=config.pool_recycle,
                pool_pre_ping=config.pool_pre_ping,
                pool_timeout=config.pool_timeout,
                echo=config.echo,
                connect_args={
                    "server_settings": {
                        "statement_timeout": str(config.statement_timeout_ms),
                    }
                },
            )
            self._async_sessionmaker = async_sessionmaker(
                self._async_engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )

            # ── 同步引擎（psycopg2 驱动，用于迁移等同步场景）──────────
            sync_url = config.url.replace("+asyncpg", "")
            self._sync_engine = create_engine(
                sync_url,
                pool_size=config.pool_size,
                max_overflow=config.max_overflow,
                pool_recycle=config.pool_recycle,
                pool_pre_ping=config.pool_pre_ping,
                echo=config.echo,
            )
            self._sync_sessionmaker = sessionmaker(
                self._sync_engine,
                class_=Session,
                expire_on_commit=False,
            )

            self._initialized = True
            logger.info("数据库管理器已初始化")

    # ── 会话获取 ────────────────────────────────────────────────────────

    @property
    def async_engine(self) -> AsyncEngine:
        """获取异步 SQLAlchemy 引擎（用于建表等直接引擎操作）。"""
        self._ensure_initialized()
        return self._async_engine

    def async_session(self) -> AsyncSession:
        """获取一个新的异步会话。

        调用方需自行管理会话生命周期（``await session.close()`` 或
        使用 ``async with`` 上下文管理器）。

        Returns:
            一个新的 ``AsyncSession`` 实例。

        Raises:
            RuntimeError: 管理器尚未初始化。
        """
        self._ensure_initialized()
        return self._async_sessionmaker()

    def sync_session(self) -> Session:
        """获取一个新的同步会话。

        调用方需自行管理会话生命周期（``session.close()`` 或
        使用 ``with`` 上下文管理器）。

        Returns:
            一个新的 ``Session`` 实例。

        Raises:
            RuntimeError: 管理器尚未初始化。
        """
        self._ensure_initialized()
        return self._sync_sessionmaker()

    # ── 资源释放 ────────────────────────────────────────────────────────

    async def close(self) -> None:
        """释放异步引擎及其连接池。"""
        if self._async_engine is not None:
            await self._async_engine.dispose()
            self._async_engine = None
            logger.info("异步数据库引擎已释放")

    def close_sync(self) -> None:
        """释放同步引擎及其连接池。"""
        if self._sync_engine is not None:
            self._sync_engine.dispose()
            self._sync_engine = None
            logger.info("同步数据库引擎已释放")

    async def dispose(self) -> None:
        """释放所有引擎资源（异步 + 同步）并重置初始化状态。

        通常在服务关闭时调用一次。
        """
        self.close_sync()
        await self.close()
        self._initialized = False
        logger.info("数据库管理器已完全释放")

    # ── 内部辅助 ────────────────────────────────────────────────────────

    def _ensure_initialized(self) -> None:
        """确保管理器已完成初始化，否则抛出明确错误。"""
        if not self._initialized:
            raise RuntimeError(
                "数据库管理器尚未初始化，请先调用 initialize()"
            )


# ── 独立工厂函数 ────────────────────────────────────────────────────────


def create_db_engine(
    url: str | None = None,
    echo: bool = False,
) -> AsyncEngine:
    """创建异步 SQLAlchemy 引擎（不需要 Nacos 配置的轻量入口）。

    用于测试、本地开发等无需完整 Nacos 配置链的场景。
    优先读取 ``DATABASE_URL`` 环境变量，否则使用内置默认值。

    Args:
        url: PostgreSQL 连接字符串（asyncpg 驱动），为 None 时从环境变量读取。
        echo: 是否打印 SQL 日志。

    Returns:
        ``sqlalchemy.ext.asyncio.AsyncEngine`` 实例。
    """
    import os

    _DEFAULT_URL = "postgresql+asyncpg://ai_finance:ai_finance_dev@127.0.0.1:5432/ai_finance"
    db_url = url or os.getenv("DATABASE_URL", _DEFAULT_URL)

    engine = create_async_engine(
        db_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    logger.info("数据库引擎已创建（独立模式）: %s", _mask_password(db_url))
    return engine


def _mask_password(url: str) -> str:
    """脱敏连接字符串中的密码。"""
    if "@" not in url:
        return url
    prefix, suffix = url.split("@", 1)
    if ":" in prefix:
        scheme_user, _ = prefix.rsplit(":", 1)
        return f"{scheme_user}:****@{suffix}"
    return url
