from __future__ import annotations
import json
import unittest
from pathlib import Path
from infrastructure.config.llm_config import LLMConfig


class LLmConfigRequestTest(unittest.TestCase):
    def test_llm_config(self):
        json_str = json.loads(Path("./config/config.json").read_text())
        llm_config = LLMConfig(**json_str)
        print(f"{llm_config}")


class SummarizationConfigTest(unittest.TestCase):
    """llm-config 的 summarization 节——默认值与 YAML 解析。"""

    def test_defaults(self) -> None:
        from infrastructure.config.llm_config import LLMConfig

        cfg = LLMConfig(api_key="k")
        self.assertTrue(cfg.summarization.enabled)
        self.assertEqual(cfg.summarization.trigger_tokens, 4000)
        self.assertEqual(cfg.summarization.keep_messages, 20)

    def test_parse_nested_node(self) -> None:
        from infrastructure.config.llm_config import LLMConfig

        cfg = LLMConfig(**{
            "api_key": "k",
            "summarization": {"enabled": False, "trigger_tokens": 800, "keep_messages": 6},
        })
        self.assertFalse(cfg.summarization.enabled)
        self.assertEqual(cfg.summarization.trigger_tokens, 800)
        self.assertEqual(cfg.summarization.keep_messages, 6)
