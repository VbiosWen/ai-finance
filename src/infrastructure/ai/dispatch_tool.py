"""技能分派工具 —— 将用户任务转发给指定 Skill 的专属子 Agent 执行。

作为 Router Agent 的执行工具，LLM 在查询技能详情后调用此工具，
将具体任务交给该技能的专用 Agent（含专属 tools + 完整 prompt）处理。
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage

from domain.ports.skill_config_repository import SkillConfigRepository
from domain.shared.ai_tools import AITool, ToolResult
from infrastructure.ai.skill_agent_factory import SkillAgentFactory

logger = logging.getLogger("ai-finance")


class DispatchToSkillTool(AITool):
    """将任务转发给指定技能的专属子 Agent 执行。

    子 Agent 持有该技能专属的 tools 和完整 prompt，Router Agent
    通过此工具将用户请求分派到正确的技能上下文。

    用法::

        dispatch = DispatchToSkillTool(factory, skill_repo)

        # LLM 调用: execute_skill(skill_name="发票稽核", task="稽核代码 3100234567")
        # → 子 Agent 执行 → 返回结果
    """

    name = "execute_skill"
    description = (
        "使用指定技能执行用户的具体任务。"
        "必须先通过 lookup_skill 了解技能详情后再调用。"
        "参数: skill_name (技能名称)、task (要执行的具体任务描述，"
        "应包含用户原始需求的关键信息)。"
    )

    def __init__(
        self,
        agent_factory: SkillAgentFactory,
        skill_repo: SkillConfigRepository,
        *,
        config_key: str = "skill-configs",
    ) -> None:
        """初始化分派工具。

        Args:
            agent_factory: 子 Agent 工厂（负责编译和缓存）。
            skill_repo: 技能配置仓储。
            config_key: 仓储中的配置 key。
        """
        self._factory = agent_factory
        self._repo = skill_repo
        self._config_key = config_key

    async def execute(self, **kwargs: str) -> ToolResult:
        """执行技能任务。

        Args:
            **kwargs: 应包含 ``skill_name``（技能名）和 ``task``（任务描述）。

        Returns:
            ToolResult: 成功时 content 为子 Agent 的最终回复文本。
        """
        skill_name = (kwargs.get("skill_name") or "").strip()
        task = (kwargs.get("task") or "").strip()

        if not skill_name:
            return ToolResult(
                success=False,
                content="缺少参数: skill_name（要使用的技能名称）",
                tool_name=self.name,
            )
        if not task:
            return ToolResult(
                success=False,
                content="缺少参数: task（要执行的具体任务）",
                tool_name=self.name,
            )

        try:
            sub_agent = self._factory.get_or_build(
                skill_name,
                self._repo,
                config_key=self._config_key,
            )
        except KeyError as exc:
            return ToolResult(
                success=False,
                content=str(exc),
                tool_name=self.name,
            )

        try:
            result = await sub_agent.ainvoke(
                {"messages": [HumanMessage(content=task)]}
            )
            reply: str = _extract_last_ai_content(result.get("messages", []))
            logger.info(
                "Skill 执行完成: skill=%s len(reply)=%d",
                skill_name,
                len(reply),
            )
            return ToolResult(success=True, content=reply, tool_name=self.name)
        except Exception:
            logger.exception("Skill 执行异常: skill=%s", skill_name)
            return ToolResult(
                success=False,
                content=f"技能「{skill_name}」执行异常，请重试或联系管理员。",
                tool_name=self.name,
            )


# ── 辅助 ──────────────────────────────────────────────────────────


def _extract_last_ai_content(messages: list[Any]) -> str:
    """从 LangGraph 消息列表中提取最后一条 AI 消息的文本内容。"""
    from langchain_core.messages import AIMessage

    for msg in reversed(messages):
        if isinstance(msg, AIMessage):
            content = msg.content
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts = [
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict)
                ]
                return "".join(parts)
            return str(content)
    return ""
