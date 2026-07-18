from pydantic import BaseModel, Field


class SkillConfig(BaseModel):
    name: str  # 技能标识
    description: str  # 技能简介
    task_instructions: str  # 该skill 具体要做什么
    examples: list[dict[str, str]] = Field(default_factory=list)  # 示例
    extra_constraints: list[str] = Field(default_factory=list)  # 该skill的专属约束
    version: str = ""

    def render_skill_block(self) -> str:
        block_skill = f"[{self.name}] {self.task_instructions} (version: {self.version})"

        if self.extra_constraints:
            rules = "\n".join(f"- {c}" for c in self.extra_constraints)
            block_skill += f"\n 专属约束：\n{rules}"

        if self.examples:
            examples = "\n".join(f"- {c}" for c in self.examples)
            block_skill += f"\n 示例：\n{examples}"
        return block_skill
