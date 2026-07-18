"""Agent 提示词配置 —— 不可变值对象。

组合 AgentIdentity + 单个 SkillConfig + 运行时参数，
为一个 Agent 提供完整的提示词渲染。

设计决策：一个 Agent 对应一个技能（单 SkillConfig），
多技能场景通过多个 Agent 实例组合实现，职责更清晰。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig


class AgentPromptConfig(BaseModel):
    """Agent 的一整套提示词配置（不可变）。"""

    agent_identity: AgentIdentity = Field(description="Agent 身份定义")
    skill: SkillConfig = Field(description="Agent 专精的单一技能")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64)

    model_config = {"frozen": True}

    def render(self) -> str:
        """渲染完整系统提示词（身份 + 技能）。"""
        return f"{self.agent_identity.render()}\n\n---\n\n{self.skill.render_skill_block()}"
