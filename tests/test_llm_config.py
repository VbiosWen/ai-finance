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
