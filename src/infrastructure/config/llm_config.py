from logging import getLogger

from anthropic import BaseModel
from pydantic import Field

logger = getLogger("ai-finance")



class LLMConfig(BaseModel):
    model : str = Field(default="deepseek-v4-pro",description="llm_model")
    api_key : str = Field(description="llm_api_key",)
    max_token : str = Field(default="1M",description="llm_max_token")
    max_retries : int = Field(default=5,description="llm_max_retries")