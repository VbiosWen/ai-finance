from typing import Any

from langchain_deepseek import ChatDeepSeek

from infrastructure.config import LLMConfig


class LLMClientFactory:
    _config : LLMConfig

    def __init__(self, config: LLMConfig):
        self._config = config

    @classmethod
    def from_config(cls, config: LLMConfig):
        return cls(config)


    def create_llm(self) -> Any:
        if self._config.model.startswith("deepseek") :
            return self._create_deep_seek()

    def _create_deep_seek(self):
        return ChatDeepSeek(
            model= self._config.model.lower(),
            api_key=self._config.api_key,
            max_tokens=None,
            temperature=0,
            max_retries=self._config.max_retries,
        )

