"""LLM 客户端工厂——根据 LLMConfig 创建 LangChain ChatModel 实例。

不继承 ChatDeepSeek，而是通过工厂方法创建原生 SDK 实例。
支持从 config.json 的 api_key 字段或环境变量读取 API Key。
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langchain_deepseek import ChatDeepSeek

from infrastructure.config.llm_config import LLMConfig

logger = logging.getLogger("ai-finance")


class LLMClientFactory:
    """LLM 工厂——从 LLMConfig 创建对应的 ChatModel。

    使用方式:
        config = LLMConfig.from_json("config/config.json")
        factory = LLMClientFactory(config)
        llm = factory.create_llm()
    """

    def __init__(self, config: LLMConfig) -> None:
        self._config = config

    # ------------------------------------------------------------------
    # 工厂方法
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: LLMConfig) -> LLMClientFactory:
        """从配置创建工厂（语义别名）。"""
        return cls(config)

    def create_llm(self) -> Any:
        """根据配置创建对应的 ChatModel 实例。

        Returns:
            BaseChatModel 实例。

        Raises:
            ValueError: 不支持的 provider 或缺少必要的 API Key。
        """
        config = self._config
        if config.model is None:
            raise ValueError("config.model 不能为空")

        provider = self._resolve_provider()

        if provider == "deepseek":
            return self._create_deepseek()
        if provider == "openai":
            return self._create_openai()
        if provider == "anthropic":
            return self._create_anthropic()

        raise ValueError(f"不支持的 provider: {provider}")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _resolve_provider(self) -> str:
        """根据 model 名称推断 provider。"""
        model = self._config.model.lower()
        if model.startswith("deepseek"):
            return "deepseek"
        if model.startswith("gpt") or model.startswith("o"):
            return "openai"
        if model.startswith("claude"):
            return "anthropic"
        return "deepseek"  # 默认走 DeepSeek（兼容你的 config）

    def _resolve_api_key(self, provider: str) -> str:
        """解析 API Key：优先用 config.api_key，其次从环境变量读取。"""
        config = self._config

        # 1. config 中直接配了 api_key（本地开发常用）
        if config.api_key:
            return config.api_key

        # 2. 从 provider 配置的 api_key_env 环境变量读取
        provider_config = getattr(config, provider, None)
        if provider_config and provider_config.api_key_env:
            api_key = os.getenv(provider_config.api_key_env)
            if api_key:
                return api_key

        # 3. 兜底：尝试常见环境变量名
        env_map = {
            "deepseek": "DEEPSEEK_API_KEY",
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(provider)
        if env_var:
            api_key = os.getenv(env_var)
            if api_key:
                return api_key

        raise ValueError(
            f"无法获取 {provider} 的 API Key："
            f"config.api_key 未设置，且环境变量也未找到。"
            f"请在 config.json 中设置 api_key 字段，或设置 {env_var} 环境变量。"
        )

    def _create_deepseek(self) -> Any:
        config = self._config
        api_key = self._resolve_api_key("deepseek")

        provider_config = config.deepseek
        base_url = provider_config.base_url if provider_config else None

        logger.info(
            "创建 ChatDeepSeek: model=%s, temperature=%.2f",
            config.model,
            config.temperature,
        )
        kwargs: dict[str, Any] = dict(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=config.max_retries,
            api_key=api_key,
        )
        if base_url is not None:
            kwargs["base_url"] = base_url
        return ChatDeepSeek(**kwargs)

    def _create_openai(self) -> Any:
        from langchain_openai import ChatOpenAI

        config = self._config
        api_key = self._resolve_api_key("openai")

        logger.info("创建 ChatOpenAI: model=%s", config.model)
        return ChatOpenAI(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=config.max_retries,
            api_key=api_key,
        )

    def _create_anthropic(self) -> Any:
        from langchain_anthropic import ChatAnthropic

        config = self._config
        api_key = self._resolve_api_key("anthropic")

        logger.info("创建 ChatAnthropic: model=%s", config.model)
        return ChatAnthropic(
            model=config.model,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            max_retries=config.max_retries,
            api_key=api_key,
        )
