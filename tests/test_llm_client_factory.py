"""LLM 客户端工厂测试——验证 LLMClientFactory 的创建逻辑。"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from infrastructure.ai.llm_client_factory import LLMClientFactory
from infrastructure.config.llm_config import LLMConfig


class TestLLMClientFactory(unittest.TestCase):
    """LLMClientFactory 单元测试。"""

    @classmethod
    def setUpClass(cls) -> None:
        """加载测试配置。"""
        config_path = Path(__file__).parent.parent / "config" / "config.json"
        if not config_path.exists():
            raise unittest.SkipTest(f"配置文件不存在: {config_path}")
        cls._config_data = json.loads(config_path.read_text())

    def test_create_factory_from_config(self) -> None:
        """从 LLMConfig 创建工厂实例。"""
        config = LLMConfig(**self._config_data)
        factory = LLMClientFactory(config)
        self.assertIsInstance(factory, LLMClientFactory)

    def test_resolve_provider_deepseek(self) -> None:
        """model 以 deepseek 开头时识别为 deepseek provider。"""
        config = LLMConfig(**self._config_data)
        factory = LLMClientFactory(config)
        self.assertEqual(factory._resolve_provider(), "deepseek")

    def test_resolve_api_key_from_config(self) -> None:
        """config.api_key 有值时直接使用，不读环境变量。"""
        config = LLMConfig(**self._config_data)
        factory = LLMClientFactory(config)
        api_key = factory._resolve_api_key("deepseek")
        self.assertTrue(api_key.startswith("sk-"))

    def test_resolve_api_key_from_env(self) -> None:
        """config.api_key 为 None 时从环境变量读取。"""
        data = {**self._config_data, "api_key": None}
        config = LLMConfig(**data)
        factory = LLMClientFactory(config)

        # 设置环境变量
        os.environ["DEEPSEEK_API_KEY"] = "sk-test-env-key"
        try:
            api_key = factory._resolve_api_key("deepseek")
            self.assertEqual(api_key, "sk-test-env-key")
        finally:
            del os.environ["DEEPSEEK_API_KEY"]

    def test_resolve_api_key_missing_raises(self) -> None:
        """无 api_key 且无环境变量时抛异常。"""
        data = {**self._config_data, "api_key": None}
        config = LLMConfig(**data)
        factory = LLMClientFactory(config)

        # 确保环境变量不存在
        os.environ.pop("DEEPSEEK_API_KEY", None)
        with self.assertRaises(ValueError):
            factory._resolve_api_key("deepseek")

    def test_create_llm_returns_chat_model(self) -> None:
        """集成测试：create_llm 返回可用的 ChatModel。

        需要有效的 API Key（config.json 中已配置）。
        若 API Key 无效，此测试会在实际 API 调用时失败。
        """
        config = LLMConfig(**self._config_data)
        factory = LLMClientFactory(config)
        llm = factory.create_llm()
        self.assertIsNotNone(llm)
        # 验证是 ChatDeepSeek 实例
        from langchain_deepseek import ChatDeepSeek
        self.assertIsInstance(llm, ChatDeepSeek)


if __name__ == "__main__":
    unittest.main()
