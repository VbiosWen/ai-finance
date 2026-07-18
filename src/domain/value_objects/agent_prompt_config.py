from pydantic import BaseModel, Field

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig


class AgentPromptConfig(BaseModel):
    agent_identity: AgentIdentity = Field(default_factory=AgentIdentity)
    skill_config: SkillConfig = Field(default_factory=SkillConfig)
    temperature: float = Field(default=0.0)
    max_tokens: int = Field(default=2048)
    extra_params: dict = Field(default_factory=dict)

    def __post_init__(self):
        if not 0.0 <= self.temperature <= 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        if self.max_tokens < 64:
            raise ValueError("Max tokens must be at least 64")

    def render(self) -> str:
        agent_identity = self.agent_identity.render()
        skill_str = self.skill_config.render_skill_block()
        return f"{agent_identity}\n{skill_str}"
