
from pydantic import BaseModel, Field
from sqlalchemy import desc


class SkillRef(BaseModel):
    name : str = Field(description="技能标识")
    description : str = Field(description="一句话描述，LLM根据此判断合适使用")
    version : str = Field(default="")

    model_config = {"frozen" : True}
