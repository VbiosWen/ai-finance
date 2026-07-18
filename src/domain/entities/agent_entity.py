from langchain_core.runnables import Runnable
from pydantic import BaseModel

from domain.value_objects.agent_prompt_config import AgentPromptConfig


class AgentId(BaseModel):
    """领域标识：Agent 名称，版本"""
    name : str
    version : str = "default"


class AgentEntity(BaseModel):
    """
    领域层Entity
    技能 Agent
    - 有唯一标识
    - 有生命周期
    - 可更新prompt 工具链
    """
    def __init__(self,agent_id : AgentId,agent_prompt_config : AgentPromptConfig,tools: list):
        self.id = agent_id
        self._prompt = agent_prompt_config
        self._tools = tools
        self._compiled : Runnable | None = None

    def update_prompt(self,new_prompt : AgentPromptConfig):
        self._prompt = new_prompt
        self._compiled = None

    @property
    def prompt(self) -> AgentPromptConfig:
        return self._prompt
