"""Agent 提示词配置 —— 不可变值对象。

组合 AgentIdentity + SkillRef/SkillConfig + 运行时参数，
为一个 Agent 提供完整的提示词渲染。

支持两种模式：
- **动态模式**（推荐）：使用 ``skill_refs``，prompt 仅渲染技能菜单，
  LLM 通过 ``lookup_skill`` 工具按需查询技能详情，节省 token。
- **内嵌模式**（兼容）：使用 ``skill``，将完整技能指令嵌入 prompt。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from domain.value_objects.skill_ref import SkillRef


class AgentPromptConfig(BaseModel):
    """Agent 的一整套提示词配置（不可变）。"""

    agent_identity: AgentIdentity = Field(description="Agent 身份定义")
    skill: list[SkillConfig] = Field(
        default_factory=list,
        max_length=8,
        description="内嵌技能（小场景可直接嵌入 prompt，无需动态查询）",
    )
    skill_refs: list[SkillRef] = Field(
        default_factory=list,
        max_length=8,
        description="技能引用列表（推荐：prompt 仅渲染菜单，LLM 按需查询）",
    )
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048, ge=64)

    model_config = {"frozen": True}

    def render(self) -> str:
        """渲染完整系统提示词。

        两种模式：
        - **动态模式**（推荐）：若 ``skill_refs`` 非空，仅渲染技能菜单，
          LLM 通过 ``lookup_skill`` 工具按需获取技能详情。
        - **内嵌模式**（兼容）：若仅有 ``skill``，将完整技能指令渲染进 prompt。

        拼装顺序：
        1. Agent 身份定义
        2. 技能菜单（动态）或完整技能块（内嵌）
        3. 运行时参数提示

        Returns:
            格式化后的完整系统提示词字符串。
        """
        blocks: list[str] = []

        # ── 第一层：身份定义 ──────────────────────────────────────
        blocks.append(self.agent_identity.render())

        # ── 第二层：技能 ──────────────────────────────────────────
        if self.skill_refs:
            # 动态模式：仅渲染菜单，LLM 按需查询
            menu = "\n".join(
                f"- **{r.name}**（v{r.version or '?'}）：{r.description}"
                for r in self.skill_refs
            )
            blocks.append(
                f"## 可用技能\n\n{menu}\n\n"
                "**工作流程**：\n"
                "1. 根据用户需求，调用 `lookup_skill` 工具查询对应技能的完整指令。\n"
                "2. 根据技能指令中的约束和示例，调用 `execute_skill` 工具执行任务。\n"
                "3. 不要在未查询技能详情的情况下直接执行任务。"
            )
        elif self.skill:
            # 内嵌模式：完整渲染（向后兼容）
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

        # ── 第三层：运行时参数提示 ────────────────────────────────
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

