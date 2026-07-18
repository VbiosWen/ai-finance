import asyncio
import json
import logging

from infrastructure.client.nacos import NacosClient
from infrastructure.config import LLMConfig

logger = logging.getLogger("ai-finance")


class NacosLLMConfigRepository:
    """LLM 配置的 Nacos 适配器。

    从 Nacos 读取 JSON 格式的 LLMConfig，缓存 + 热更新。
    """

    def __init__(self, nacos_client: NacosClient) -> None:
        self._nacos_client = nacos_client
        self._data_id = "llm-config"
        self._group = "AI_FINANCE"
        self._config: LLMConfig | None = None
        self._loaded = False
        self._load_lock = asyncio.Lock()

    # ── 初始化 ────────────────────────────────────────────

    async def load(self) -> None:
        """从 Nacos 拉取并注册 watcher（幂等，并发安全）。"""
        async with self._load_lock:
            if self._loaded:
                return

            raw = await self._nacos_client.get_config(
                data_id=self._data_id, group=self._group
            )
            if raw:
                self._config = LLMConfig(**json.loads(raw))
                logger.info("LLMConfig 已加载: model=%s", self._config.model)
            else:
                logger.warning(
                    "Nacos 中缺少 %s/%s 配置", self._data_id, self._group
                )

            # watcher 无论是否有初始配置都注册，等配置推上来时自动热更新
            await self._nacos_client.add_watcher(
                self._data_id,
                self._group,
                self._on_config_changed,
            )
            self._loaded = True

    # ── 读取 ──────────────────────────────────────────────

    def get(self) -> LLMConfig:
        """同步获取缓存的 LLMConfig。

        Raises:
            RuntimeError: 尚未调用 load()。
            ValueError: 配置为空（Nacos 中不存在）。
        """
        if not self._loaded:
            raise RuntimeError("LLMConfigRepository 尚未加载，请先调用 load()")
        if self._config is None:
            raise ValueError("LLMConfig 为空，Nacos 中可能不存在该配置")
        return self._config

    # ── 内部 ──────────────────────────────────────────────

    def _on_config_changed(self, raw: str) -> None:
        try:
            self._config = LLMConfig(**json.loads(raw))
            logger.info("LLMConfig 已热更新: model=%s", self._config.model)
        except Exception:
            logger.exception("LLMConfig 热更新解析失败")