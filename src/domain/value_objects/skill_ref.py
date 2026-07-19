"""技能轻量引用 —— 不可变值对象。

与 ``SkillConfig`` 不同，SkillRef 仅含技能的标识与一句话简介，
不包含完整指令。用于 Agent 系统提示词中的技能菜单渲染。
"""

from pydantic import BaseModel, Field


class SkillRef(BaseModel):
    """技能的轻量引用（名称 + 简介）。

    LLM 阅读此引用判断是否需要该技能，需要时通过 ``lookup_skill`` 工具
    查询 ``SkillConfig`` 获取完整指令。
    """

    name: str = Field(description="技能标识，如 '发票稽核'")
    description: str = Field(description="一句话描述，LLM 据此判断何时使用")
    version: str = Field(default="", description="技能版本号")

    model_config = {"frozen": True}
