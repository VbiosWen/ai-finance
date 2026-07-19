"""数据库引擎配置——基于 SQLAlchemy 2.0 + asyncpg 的异步引擎工厂。

环境变量
--------
DATABASE_URL
    PostgreSQL 连接字符串，格式：
    ``postgresql+asyncpg://user:pass@host:5432/dbname``
    未设置时回退到本地默认值。
"""

from __future__ import annotations

import os
import logging

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

logger = logging.getLogger("ai-finance")

# ── 默认值 ─────────────────────────────────────────────────────────────────

_DEFAULT_URL = "postgresql+asyncpg://ai_finance:ai_finance_dev@127.0.0.1:5432/ai_finance"


# ── 配置模型 ───────────────────────────────────────────────────────────────


class DatabaseConfig(BaseModel):
    """数据库连接配置。"""

    url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", _DEFAULT_URL),
        description="PostgreSQL 连接字符串（asyncpg 驱动）",
    )

    model_config = {"frozen": True}


# ── 引擎工厂 ───────────────────────────────────────────────────────────────


def create_db_engine(
    url: str | None = None,
    echo: bool = False,
) -> AsyncEngine:
    """创建异步 SQLAlchemy 引擎。

    Args:
        url: 数据库连接字符串，为 None 时从环境变量 DATABASE_URL 读取。
        echo: 是否打印 SQL 日志（调试用）。

    Returns:
        ``sqlalchemy.ext.asyncio.AsyncEngine`` 实例。
    """
    db_url = url or os.getenv("DATABASE_URL", _DEFAULT_URL)

    engine = create_async_engine(
        db_url,
        echo=echo,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
    )
    logger.info("数据库引擎已创建: %s", _mask_password(db_url))
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
