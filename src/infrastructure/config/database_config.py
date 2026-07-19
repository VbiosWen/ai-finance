"""PostgreSQL 数据库连接配置模型。

环境变量
--------
DATABASE_URL
    PostgreSQL 连接字符串，格式：
    ``postgresql+asyncpg://user:pass@host:5432/dbname``
    未设置时回退到本地默认值。
"""

from __future__ import annotations

import os
from logging import getLogger

from anthropic import BaseModel
from pydantic import Field

logger = getLogger("ai-finance")

# ── 默认值 ─────────────────────────────────────────────────────────────────

_DEFAULT_URL = "postgresql+asyncpg://ai_finance:ai_finance_dev@127.0.0.1:5432/ai_finance"


# ── 配置模型 ───────────────────────────────────────────────────────────────


class PostgresConfig(BaseModel):
    """PostgreSQL 数据库连接配置。

    支持通过环境变量 ``DATABASE_URL`` 覆盖连接字符串，同时提供连接池参数
    的细粒度控制。
    """

    db_dsn: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", _DEFAULT_URL),
        description="PostgreSQL 连接字符串（asyncpg 驱动）",
    )

    # 连接池配置
    pool_size: int = Field(
        default=10,
        description="连接池大小（常驻连接数）",
    )
    max_overflow: int = Field(
        default=20,
        description="连接池最大溢出数（超出 pool_size 的临时连接上限）",
    )
    pool_pre_ping: bool = Field(
        default=True,
        description="从池中取出连接前先发送 ping 验证有效性",
    )
    echo: bool = Field(
        default=False,
        description="是否打印 SQL 日志（调试用，生产环境务必关闭）",
    )

    model_config = {"frozen": True}

    # ── 派生属性 ──────────────────────────────────────────────────────────

    @property
    def url(self) -> str:
        """获取完整的数据库连接 URL（与 db_dsn 等价，提供语义化别名）。"""
        return self.db_dsn
