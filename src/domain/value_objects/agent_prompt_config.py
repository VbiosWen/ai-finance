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
    skill: list[SkillConfig] = Field(description="Agent关联的技能", max_length=8)
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64)

    model_config = {"frozen": True}

    def render(self) -> str:
        """渲染完整系统提示词（身份 + 全部技能）。

        拼装顺序：
        1. Agent 身份定义（persona、语气、输出规范、全局约束）
        2. 全部技能的 skill block（任务说明 + 专属约束 + 示例）
        3. 运行时参数提示（temperature / max_tokens 仅在非默认时有提示）

        Returns:
            格式化后的完整系统提示词字符串。
        """
        blocks: list[str] = []

        # ── 第一层：身份定义 ──────────────────────────────────────
        blocks.append(self.agent_identity.render())

        # ── 第二层：技能列表 ──────────────────────────────────────
        if self.skill:
            skill_blocks: list[str] = []
            for s in self.skill:
                skill_blocks.append(s.render_skill_block())

            if len(self.skill) == 1:
                blocks.append(f"## 当前技能\n\n{skill_blocks[0]}")
            else:
                numbered = "\n\n".join(
                    f"### 技能 {i}: {block}"
                    for i, block in enumerate(skill_blocks, start=1)
                )
                blocks.append(f"## 可用技能（共 {len(self.skill)} 个）\n\n{numbered}")

        # ── 第三层：提示（仅在非默认时） ──────────────────────────
        hints: list[str] = []
        if self.temperature > 0.0:
            hints.append(f"temperature={self.temperature}")
        if self.max_tokens != 2048:
            hints.append(f"max_tokens={self.max_tokens}")
        if hints:
            blocks.append(
                f"## 运行时参数\n\n（以下为参考参数，无需在回复中提及）\n"
                + ", ".join(hints)
            )

        return "\n\n".join(blocks)

