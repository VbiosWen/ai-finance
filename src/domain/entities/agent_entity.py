"""Agent 聚合根 —— AI 技能 Agent 的领域模型。

Agent 是聚合根，持有：
- 唯一标识 (AgentId)
- 配置快照 (AgentPromptConfig，不可变值对象)
- 工具端口 (list[AITool])
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from domain.shared.ai_tools import AITool
from domain.value_objects.agent_prompt_config import AgentPromptConfig


# ---------------------------------------------------------------------------
# 标识值对象
# ---------------------------------------------------------------------------


class AgentId(BaseModel):
    """Agent 唯一标识。"""

    name: str = Field(description="Agent 名称")
    version: str = Field(default="default", description="版本号")

    model_config = {"frozen": True}

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"


# ---------------------------------------------------------------------------
# 聚合根
# ---------------------------------------------------------------------------


class AgentEntity(BaseModel):
    """AI 技能 Agent 聚合根。

    职责：
    - 持有 Agent 的身份标识和配置
    - 管理工具链
    - 对外暴露提示词渲染

    注意：领域层不含任何 LangChain / LLM 框架依赖。
    编译为可执行 Agent 的工作由基础设施层完成。
    """

    model_config = {"arbitrary_types_allowed": True}

    agent_id: AgentId = Field(description="Agent 唯一标识")
    prompt_config: AgentPromptConfig = Field(description="提示词配置快照")
    tools: list[AITool] = Field(default_factory=list, description="领域工具列表")

    # ── 领域行为 ──────────────────────────────────────────

    def update_prompt(self, new_config: AgentPromptConfig) -> None:
        """更新提示词配置。

        配置更新后，基础设施层需重新编译 agent。
        """
        self.prompt_config = new_config

    def add_tool(self, tool: AITool) -> None:
        """添加领域工具。"""
        existing = {t.name for t in self.tools}
        if tool.name in existing:
            raise ValueError(f"工具 '{tool.name}' 已存在，不允许重复添加")
        self.tools.append(tool)

    def remove_tool(self, tool_name: str) -> None:
        """移除指定工具。"""
        self.tools = [t for t in self.tools if t.name != tool_name]

    def render_prompt(self) -> str:
        """渲染完整系统提示词（身份 + 技能）。"""
        return self.prompt_config.render()

    @property
    def tool_names(self) -> list[str]:
        """当前工具名称列表（只读）。"""
        return [t.name for t in self.tools]
