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
    def test_create_llm(self):
        llm_config = LLMConfig.load()
        client_factory = LLMClientFactory.from_config(llm_config)
        llm = client_factory.create_llm()
        messages = [
            (
                "system",
                "You are a helpful assistant that translates English to French. Translate the user sentence.",
            ),
            ("human", "I love programming."),
        ]
        ai_msg = llm.invoke(messages)
        print("ai_msg:", ai_msg)

