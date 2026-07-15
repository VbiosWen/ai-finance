import json
from logging import getLogger
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

logger = getLogger("ai-finance")



class LLMConfig(BaseModel):
    model : str = Field(default="deepseek-v4-pro",description="llm_model")
    api_key : str = Field(description="llm_api_key",)
    max_token : str = Field(default="1M",description="llm_max_token")
    max_retries : int = Field(default=5,description="llm_max_retries")


    @classmethod
    def load(cls):
       _json =  json.loads(Path("config/config.json").read_text())
       try:
           return cls(**_json)
       except ValidationError as e:
           missing = [
               e["loc"][0]
               for err in e.errors()
               if err["type"] == "missing"
           ]
           logger.error(f"缺少必填字段：{missing}")
           raise e