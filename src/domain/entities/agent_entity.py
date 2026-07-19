"""Agent 聚合根 —— AI 技能 Agent 的领域模型。

支持两种运行模式：
- **单技能模式**：持有 SkillConfig + 业务工具，prompt 内嵌完整指令。
- **路由模式**：持有 SkillRef 列表 + SkillLookupTool，
  LLM 按需查询技能详情，再由 DispatchToSkillTool 分派到子 Agent 执行。
  子 Agent 各自持有专属 tools，实现动态工具注入。

多技能场景通过 Router Agent + SkillAgentFactory 组合实现。
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from domain.ports.skill_config_repository import SkillConfigRepository
from domain.shared.ai_tools import AITool
from domain.tools.skill_lookup import SkillLookupTool
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

    def build_tools(
        self,
        skill_repo: SkillConfigRepository,
        *,
        config_key: str = "skill-configs",
    ) -> list[AITool]:
        """装配该 Agent 的工具链。

        若 prompt_config 使用了 skill_refs（动态模式），自动注入
        ``SkillLookupTool`` 让 LLM 按需查询技能详情。

        若使用内嵌模式（skill），仅返回业务工具。

        Args:
            skill_repo: 技能配置仓储。
            config_key: 仓储中技能配置的 key。

        Returns:
            完整的 AITool 列表（业务工具 + 必要时含 SkillLookupTool）。
        """
        tools: list[AITool] = list(self.tools)

        if self.prompt_config.skill_refs:
            tools.append(
                SkillLookupTool(
                    skill_repo,
                    self.prompt_config.skill_refs,
                    config_key=config_key,
                )
            )

        return tools

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
