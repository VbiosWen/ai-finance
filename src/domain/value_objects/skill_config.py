from pydantic import BaseModel, Field


class SkillConfig(BaseModel):
    """单个技能的完整配置（不可变）。"""

    name: str = Field(description="技能标识")
    description: str = Field(description="技能简介")
    task_instructions: str = Field(description="该技能具体要做什么")
    tool_names: list[str] = Field(
        default_factory=list,
        description="该技能依赖的工具名称列表",
    )
    examples: list[dict[str, str]] = Field(default_factory=list, description="示例")
    extra_constraints: list[str] = Field(default_factory=list, description="该技能的专属约束")
    version: str = Field(default="", description="版本号")

    model_config = {"frozen": True}

    def render_skill_block(self) -> str:
        block_skill = f"[{self.name}] {self.task_instructions} (version: {self.version})"

        if self.extra_constraints:
            rules = "\n".join(f"- {c}" for c in self.extra_constraints)
            block_skill += f"\n 专属约束：\n{rules}"

        if self.examples:
            examples = "\n".join(f"- {c}" for c in self.examples)
            block_skill += f"\n 示例：\n{examples}"
        return block_skill
