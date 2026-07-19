"""SkillConfig 的 Nacos 适配器 —— 实现 domain 层的 SkillConfigRepository 端口。

从 Nacos YAML 数组配置读取技能列表，缓存 + 热更新。
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable

import yaml

from domain.ports.prompt_repository import SkillConfigRepository
from domain.value_objects.skill_config import SkillConfig
from infrastructure.client.nacos import NacosClient
from infrastructure.ports.nacos_config_repository import NacosConfigRepository

logger = logging.getLogger("ai-finance")


class NacosSkillConfigRepository(SkillConfigRepository,NacosConfigRepository):
    """从 Nacos 读取 SkillConfig 列表，支持热更新。

    用法::

        repo = NacosSkillConfigRepository(client, data_id="skill-configs")
        await repo.load()
        skills = repo.get("skill-configs")
        repo.watch(on_skills_changed)
    """

    def __init__(
        self,
        nacos_client: NacosClient,
        *,
        data_id: str = "skill-configs",
        group: str = "AI_FINANCE",
    ) -> None:
        self._client = nacos_client
        self._data_id = data_id
        self._group = group
        self._cache: dict[str, list[SkillConfig]] = {}
        self._watchers: list[Callable[[list[SkillConfig]], None]] = []
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
                items = yaml.safe_load(raw)
                skills = [SkillConfig(**item) for item in items]
                self._cache[self._data_id] = skills
                logger.info(
                    "SkillConfig 已加载: data_id=%s count=%d",
                    self._data_id,
                    len(skills),
                )
            else:
                logger.warning(
                    "Nacos 中无 SkillConfig 配置: data_id=%s", self._data_id
                )
                self._cache[self._data_id] = []

            await self._client.add_watcher(
                self._data_id,
                self._group,
                self._on_config_changed,
            )
            self._loaded = True

    # ── SkillConfigRepository 接口实现 ─────────────────────

    def get(self, key: str) -> list[SkillConfig]:
        if not self._loaded:
            raise RuntimeError("NacosSkillConfigRepository 尚未加载，请先调用 load()")
        return self._cache.get(key, [])

    def watch(self, callback: Callable[[list[SkillConfig]], None]) -> None:
        self._watchers.append(callback)
        logger.info(
            "SkillConfig watcher 已注册（当前 %d 个订阅者）", len(self._watchers)
        )

    # ── 内部 ──────────────────────────────────────────────

    def _on_config_changed(self, raw: str) -> None:
        try:
            items = yaml.safe_load(raw)
            skills = [SkillConfig(**item) for item in items]
            self._cache[self._data_id] = skills
            logger.info("SkillConfig 已热更新: count=%d", len(skills))
        except Exception:
            logger.exception("SkillConfig 热更新解析失败")
            return

        for cb in self._watchers:
            try:
                cb(skills)
            except Exception:
                logger.exception("SkillConfig watcher 回调异常")
