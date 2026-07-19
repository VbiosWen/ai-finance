"""技能查询工具 —— 让 LLM 按需获取技能完整指令。

作为 Router Agent 的元工具，LLM 在选择技能后调用此工具获取
该技能的 task_instructions、constraints、examples 等完整信息。
"""

from __future__ import annotations

from domain.ports.skill_config_repository import SkillConfigRepository
from domain.shared.ai_tools import AITool, ToolResult
from domain.value_objects.skill_ref import SkillRef


class SkillLookupTool(AITool):
    """按名称查询技能详情。

    在 Router Agent 中注册，让 LLM 先看菜单再获取完整指令。
    避免把所有技能的详细 prompt 全部塞进系统提示词。

    用法::

        tool = SkillLookupTool(skill_repo, skill_refs)

        # LLM 调用: lookup_skill("发票稽核")
        # 返回: 完整的 skill block（task_instructions + constraints + examples）
    """

    name = "lookup_skill"
    description = (
        "查询指定技能的完整操作说明、约束条件和示例。"
        "在使用技能前必须先调用此工具获取详细指令，不要凭菜单简介猜测。"
        '参数: skill_name (技能名称，如 "发票稽核")。'
    )

    def __init__(
        self,
        skill_repo: SkillConfigRepository,
        skill_refs: list[SkillRef],
        *,
        config_key: str = "skill-configs",
    ) -> None:
        """初始化技能查询工具。

        Args:
            skill_repo: 技能配置仓储（含完整 SkillConfig）。
            skill_refs: 技能引用列表（用于构建菜单）。
            config_key: 仓储中技能配置的 key。
        """
        self._repo = skill_repo
        self._refs: dict[str, SkillRef] = {r.name: r for r in skill_refs}

    async def execute(self, **kwargs: str) -> ToolResult:
        """查询技能详情。

        Args:
            **kwargs: 应包含 ``skill_name``（要查询的技能名）。
                      若为空或 "list" 则返回可用技能菜单。

        Returns:
            ToolResult: 成功时 content 为完整 skill block 文本。
        """
        name = (kwargs.get("skill_name") or "").strip()

        # ── 列出可用技能 ────────────────────────────────────────
        if not name or name == "list":
            if not self._refs:
                return ToolResult(True, "暂无可用技能。", self.name)
            menu = "\n".join(
                f"- **{r.name}**（v{r.version or '?'}）：{r.description}"
                for r in self._refs.values()
            )
            return ToolResult(
                success=True,
                content=f"可用技能列表：\n{menu}\n\n请选择技能后再次调用 lookup_skill(skill_name=\"<技能名>\")。",
                tool_name=self.name,
            )

        # ── 校验技能名 ──────────────────────────────────────────
        if name not in self._refs:
            available = "、".join(self._refs.keys())
            return ToolResult(
                success=False,
                content=f"未知技能「{name}」。可用技能：{available}",
                tool_name=self.name,
            )

        # ── 从仓储查找完整 SkillConfig ─────────────────────────
        skills = self._repo.get(name)
        for skill in skills:
            if skill.name == name:
                return ToolResult(
                    success=True,
                    content=(
                        f"## {skill.name}（v{skill.version}）\n\n"
                        f"{skill.render_skill_block()}"
                    ),
                    tool_name=self.name,
                )

        return ToolResult(
            success=False,
            content=f"技能「{name}」在配置中未找到详情，请联系管理员。",
            tool_name=self.name,
        )
