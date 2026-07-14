"""LLM 配置 Schema——定义 LLM provider 配置的结构。

JSON 配置文件放在项目根目录 config/ 下。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field


class ProviderConfig(BaseModel):
    """单个 provider 的配置。"""

    api_key_env: str = Field(
        default="",
        description="API Key 所在的环境变量名称",
    )
    base_url: str | None = Field(
        default=None,
        description="自定义 API 地址",
    )


class LLMConfig(BaseModel):
    """LLM 配置。

    JSON 文件示例 (config/config.example.json):
    ```json
    {
        "model": "deepseek-chat",
        "api_key": null,
        "temperature": 0.1,
        "max_tokens": 4096,
        "max_retries": 3
    }
    ```
    """

    model: str = Field(description="模型名称，如 deepseek-chat、gpt-4o 等")
    api_key: str | None = Field(
        default=None,
        description="API Key（可选）。优先用此字段，为 None 时从 api_key_env 环境变量读取",
    )
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1)
    max_retries: int = Field(default=3, ge=0)

    # provider 特有配置
    deepseek: ProviderConfig | None = None
    openai: ProviderConfig | None = None
    anthropic: ProviderConfig | None = None

    @classmethod
    def from_json(cls, path: str | Path) -> LLMConfig:
        """从 JSON 文件加载配置。"""
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)
