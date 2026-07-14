"""LLM 工厂测试——验证 LLMClientFactory 的创建与参数处理。"""
from __future__ import annotations

import unittest

from infrastructure.ai.llm_client import LLMClientFactory


class LLMClientFactoryTest(unittest.TestCase):
    """LLMClientFactory 单元测试。"""

    def test_create_factory_openai(self) -> None:
        """创建 OpenAI provider 工厂。"""
        factory = LLMClientFactory(provider="openai")
        self.assertEqual(factory.provider, "openai")

    def test_create_factory_anthropic(self) -> None:
        """创建 Anthropic provider 工厂。"""
        factory = LLMClientFactory(provider="anthropic")
        self.assertEqual(factory.provider, "anthropic")

    def test_create_factory_case_insensitive(self) -> None:
        """provider 名称大小写不敏感。"""
        factory = LLMClientFactory(provider="AnThRoPiC")
        self.assertEqual(factory.provider, "anthropic")

    def test_create_factory_unsupported_provider(self) -> None:
        """不支持的 provider 抛出 ValueError。"""
        with self.assertRaises(ValueError):
            LLMClientFactory(provider="unsupported")

    def test_create_chat_model_without_api_key_raises(self) -> None:
        """无 API Key 时抛出 RuntimeError。"""
        factory = LLMClientFactory(provider="openai")
        with self.assertRaises(RuntimeError):
            factory.create_chat_model()


if __name__ == "__main__":
    unittest.main()
