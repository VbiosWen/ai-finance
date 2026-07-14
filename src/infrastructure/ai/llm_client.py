"""LLM 客户端工厂——实现 application.ports.LLMFactory 端口。

根据配置创建 LangChain BaseChatModel 实例，支持多 provider 切换。
Provider 选择通过环境变量 LLM_PROVIDER 或构造函数参数指定。
"""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger("ai-finance")


class LLMClientFactory:
    """LLM 工厂实现，创建 LangChain ChatModel。

    支持的 provider:
    - openai: ChatOpenAI（需要 OPENAI_API_KEY）
    - anthropic: ChatAnthropic（需要 ANTHROPIC_API_KEY）

    使用示例:
        factory = LLMClientFactory(provider="anthropic")
        llm = factory.create_chat_model(temperature=0.1)
    """

    def __init__(self, provider: str | None = None) -> None:
        """初始化 LLM 工厂。

        Args:
            provider: LLM provider 名称（"openai" 或 "anthropic"）。
                      为 None 时从环境变量 LLM_PROVIDER 读取，
                      环境变量也未设时默认 "openai"。
        """
        self._provider = (provider or os.getenv("LLM_PROVIDER", "openai")).lower()
        if self._provider not in ("openai", "anthropic"):
            raise ValueError(
                f"不支持的 LLM provider: {self._provider}，可选值: openai, anthropic"
            )

    @property
    def provider(self) -> str:
        """当前使用的 provider 名称。"""
        return self._provider

    def create_chat_model(
        self,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """创建 LangChain BaseChatModel 实例。

        Args:
            temperature: 温度参数，默认 0.1（低温度提高工具选择确定性）。
            max_tokens: 最大输出 token 数，None 表示使用模型默认值。
            **kwargs: provider 特有的额外参数，透传给 ChatModel 构造函数。

        Returns:
            BaseChatModel 实例（ChatOpenAI 或 ChatAnthropic）。

        Raises:
            ValueError: provider 不支持。
            RuntimeError: 缺少必需的 API Key。
        """
        if self._provider == "openai":
            return self._create_openai(
                temperature=temperature, max_tokens=max_tokens, **kwargs
            )
        return self._create_anthropic(
            temperature=temperature, max_tokens=max_tokens, **kwargs
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _create_openai(
        self,
        temperature: float,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> Any:
        """创建 ChatOpenAI 实例。"""
        from langchain_openai import ChatOpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY 环境变量未设置，无法创建 ChatOpenAI 实例"
            )

        model = kwargs.pop("model", os.getenv("OPENAI_MODEL", "gpt-4o"))
        base_url = kwargs.pop("base_url", os.getenv("OPENAI_BASE_URL", None))

        logger.info(
            "创建 ChatOpenAI: model=%s, temperature=%.2f, max_tokens=%s",
            model,
            temperature,
            max_tokens,
        )
        return ChatOpenAI(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            base_url=base_url,
            **kwargs,
        )

    def _create_anthropic(
        self,
        temperature: float,
        max_tokens: int | None,
        **kwargs: Any,
    ) -> Any:
        """创建 ChatAnthropic 实例。"""
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY 环境变量未设置，无法创建 ChatAnthropic 实例"
            )

        model = kwargs.pop("model", os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-20251001"))

        logger.info(
            "创建 ChatAnthropic: model=%s, temperature=%.2f, max_tokens=%s",
            model,
            temperature,
            max_tokens,
        )
        return ChatAnthropic(
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            api_key=api_key,
            **kwargs,
        )
