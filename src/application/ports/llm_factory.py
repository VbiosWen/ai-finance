"""LLM 工厂端口——定义创建 ChatModel 的抽象契约。

应用层依赖此端口，基础设施层对接具体 LLM provider（OpenAI、Anthropic 等）。
"""
from __future__ import annotations

from typing import Any, Protocol


class LLMFactory(Protocol):
    """LLM 工厂抽象端口。

    定义创建 LangChain BaseChatModel 实例的标准方法，
    隐藏具体 provider 的配置细节。
    """

    def create_chat_model(
        self,
        *,
        temperature: float = 0.1,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> Any:
        """创建并返回 LangChain ChatModel 实例。

        Args:
            temperature: 温度参数，默认 0.1（低温度提高工具选择确定性）。
            max_tokens: 最大输出 token 数，None 表示使用模型默认值。
            **kwargs: provider 特有的额外参数。

        Returns:
            BaseChatModel 实例（如 ChatOpenAI、ChatAnthropic）。
        """
        ...
