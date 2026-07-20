from logging import getLogger

from pydantic import BaseModel, Field

logger = getLogger("ai-finance")


class SummarizationConfig(BaseModel):
    """轮次压缩(SummarizationMiddleware)配置——Nacos llm-config 的 summarization 节。"""

    enabled: bool = Field(default=True, description="是否启用轮次压缩")
    trigger_tokens: int = Field(default=4000, description="触发压缩的 token 阈值")
    keep_messages: int = Field(default=20, description="压缩后保留的最近消息条数")


class LLMConfig(BaseModel):
    model: str = Field(default="deepseek-v4-pro", description="llm_model")
    api_key: str = Field(description="llm_api_key")
    max_token: str = Field(default="1M", description="llm_max_token")
    max_retries: int = Field(default=5, description="llm_max_retries")
    summarization: SummarizationConfig = Field(
        default_factory=SummarizationConfig, description="轮次压缩配置"
    )
