"""Agent 提示词配置 —— 不可变值对象。

组合 AgentIdentity + SkillConfig[] + 运行时参数，
为一个 Agent 提供完整的提示词渲染。
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig


class AgentPromptConfig(BaseModel):
    """Agent 的一整套提示词配置（不可变）。"""

    agent_identity: AgentIdentity = Field(description="Agent 身份定义")
    skills: list[SkillConfig] = Field(default_factory=list, description="技能列表")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64)

    model_config = {"frozen": True}

    @model_validator(mode="after")
    def _validate_temperature(self) -> "AgentPromptConfig":
        """业务不变量：temperature 必须在 [0.0, 2.0] 范围内。"""
        # 已由 Field(ge=0.0, le=2.0) 自动校验，此处保留作为显式不变量文档
        return self

    def render(self) -> str:
        """渲染完整系统提示词。"""
        parts = [self.agent_identity.render()]
        for skill in self.skills:
            parts.append(skill.render_skill_block())
        return "\n\n---\n\n".join(parts)
