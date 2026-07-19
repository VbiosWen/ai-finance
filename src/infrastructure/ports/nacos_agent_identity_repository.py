"""AgentIdentity 的 Nacos 适配器 —— 实现 domain 层的 AgentIdentityRepository 端口。

从 Nacos YAML 配置读取 Agent 身份定义，缓存 + 热更新。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

import yaml

from domain.ports.agent_identity_repository import AgentIdentityRepository
from domain.value_objects.agent_identity import AgentIdentity
from infrastructure.client.nacos import NacosClient
from infrastructure.ports.nacos_config_repository import NacosConfigRepository

logger = logging.getLogger("ai-finance")


class NacosAgentIdentityRepository(AgentIdentityRepository,NacosConfigRepository):
    """从 Nacos 读取 AgentIdentity，支持热更新。

    用法::

        repo = NacosAgentIdentityRepository(client, data_id="agent-identity")
        await repo.load()
        identity = repo.get("agent-identity")
        repo.watch(on_identity_changed)
    """

    def __init__(
        self,
        nacos_client: NacosClient,
        *,
        data_id: str = "agent-identity",
        group: str = "AI_FINANCE",
    ) -> None:
        self._client = nacos_client
        self._data_id = data_id
        self._group = group
        self._cache: dict[str, AgentIdentity] = {}
        self._watchers: list[Callable[[AgentIdentity], None]] = []
        self._loaded = False
        self._load_lock = asyncio.Lock()

    # ── 初始化 ────────────────────────────────────────────

    async def load(self) -> None:
        """从 Nacos 拉取并注册 watcher（幂等，并发安全）。"""
        async with self._load_lock:
            if self._loaded:
                return

            raw = await self._client.get_config(self._data_id, self._group)
            if raw:
                identity = AgentIdentity(**yaml.safe_load(raw))
                self._cache[self._data_id] = identity
                logger.info(
                    "AgentIdentity 已加载: data_id=%s persona=%s",
                    self._data_id,
                    identity.persona,
                )
            else:
                logger.warning(
                    "Nacos 中无 AgentIdentity 配置: data_id=%s", self._data_id
                )

            await self._client.add_watcher(
                self._data_id,
                self._group,
                self._on_config_changed,
            )
            self._loaded = True

    # ── AgentIdentityRepository 接口实现 ───────────────────

    def get(self, key: str) -> AgentIdentity:
        if not self._loaded:
            raise RuntimeError("NacosAgentIdentityRepository 尚未加载，请先调用 load()")
        if key not in self._cache:
            raise KeyError(f"AgentIdentity 不存在: key={key}")
        return self._cache[key]

    def watch(self, callback: Callable[[AgentIdentity], None]) -> None:
        self._watchers.append(callback)
        logger.info(
            "AgentIdentity watcher 已注册（当前 %d 个订阅者）", len(self._watchers)
        )

    # ── 内部 ──────────────────────────────────────────────

    def _on_config_changed(self, raw: str) -> None:
        try:
            data = yaml.safe_load(raw)
            identity = AgentIdentity(**data)
            self._cache[self._data_id] = identity
            logger.info("AgentIdentity 已热更新: persona=%s", identity.persona)
        except Exception:
            logger.exception("AgentIdentity 热更新解析失败")
            return

        for cb in self._watchers:
            try:
                cb(identity)
            except Exception:
                logger.exception("AgentIdentity watcher 回调异常")
