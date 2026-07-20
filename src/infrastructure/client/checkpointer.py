"""LangGraph Postgres checkpointer 接入助手。

AsyncPostgresSaver 走 psycopg3 直连(非 SQLAlchemy),与业务表共库不同表;
DSN 需从项目统一的 SQLAlchemy 格式(postgresql+asyncpg://)剥掉方言后缀。
"""
from __future__ import annotations

from contextlib import AsyncExitStack

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


def to_psycopg_dsn(dsn: str) -> str:
    """把 SQLAlchemy 方言 DSN(scheme+driver://)转为 psycopg 直连 DSN。"""
    scheme, sep, rest = dsn.partition("://")
    if not sep:
        return dsn
    return scheme.split("+", 1)[0] + "://" + rest


async def open_postgres_checkpointer(
    stack: AsyncExitStack, dsn: str
) -> AsyncPostgresSaver:
    """打开 AsyncPostgresSaver 并建 checkpoint 表。

    生命周期挂入 stack,随 Container.shutdown() 逆序关闭;
    setup() 建表沿用 create_conversation_tables 的 MVP 模式(正式迁移待 Alembic)。
    启动期 Postgres 不可达 → 直接抛错(fail-fast,不静默降级为无记忆)。
    """
    saver = await stack.enter_async_context(
        AsyncPostgresSaver.from_conn_string(to_psycopg_dsn(dsn))
    )
    await saver.setup()
    return saver
