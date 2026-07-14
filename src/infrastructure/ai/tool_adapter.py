"""工具适配器——将领域层 AITool 端口适配为 LangChain Tool。

领域层定义工具的语义（做什么），基础设施层完成框架包装（怎么做）。
此模块负责把 AITool 实例转换为 LangChain create_agent 可接受的 Tool 对象。
"""
from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.tools import tool as langchain_tool

from domain.shared.ai_tools import AITool, ToolResult

logger = logging.getLogger("ai-finance")


def adapt_ai_tool(ai_tool: AITool) -> Any:
    """将单个领域 AITool 适配为 LangChain Tool。

    生成一个异步 LangChain Tool，其输入为 JSON 字符串（键值对），
    内部解析后调用 AITool.execute(**params)，并将 ToolResult 转为纯文本返回。

    Args:
        ai_tool: 实现了 AITool 端口的领域工具实例。

    Returns:
        LangChain Tool 对象，可直接传入 create_agent(tools=[...])。

    Example:
        >>> from domain.shared.ai_tools import AITool, ToolResult
        >>>
        >>> class MockTool(AITool):
        ...     name = "greet"
        ...     description = "向用户打招呼。参数: name (姓名)"
        ...     async def execute(self, **kwargs):
        ...         return ToolResult(True, f"你好, {kwargs.get('name', '世界')}!", "greet")
        >>>
        >>> langchain_tool = adapt_ai_tool(MockTool())
    """

    async def _execute(input: str = "") -> str:
        """执行领域工具并返回结果文本。

        Args:
            input: JSON 键值对字符串，如 '{"invoice_id": "INV-001"}'。

        Returns:
            工具执行结果文本，或错误描述。
        """
        params: dict[str, str] = {}
        stripped = input.strip() if input else ""

        if stripped:
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, dict):
                    params = {str(k): str(v) for k, v in parsed.items()}
                else:
                    params = {"query": str(parsed)}
            except json.JSONDecodeError:
                params = {"query": input}

        try:
            result: ToolResult = await ai_tool.execute(**params)
        except Exception as exc:
            logger.error("工具 %s 执行异常: %s", ai_tool.name, exc)
            return f"工具执行异常: {exc}"

        if result.success:
            logger.debug(
                "工具 %s 执行成功，内容长度=%d",
                result.tool_name,
                len(result.content),
            )
            return result.content

        logger.warning("工具 %s 执行失败: %s", result.tool_name, result.error)
        return f"工具执行失败: {result.error}"

    decorated = langchain_tool(ai_tool.name, description=ai_tool.description)
    return decorated(_execute)


def adapt_ai_tools(tools: list[AITool]) -> list[Any]:
    """批量将领域 AITool 列表适配为 LangChain Tool 列表。

    Args:
        tools: AITool 实例列表。

    Returns:
        LangChain Tool 对象列表。
    """
    return [adapt_ai_tool(t) for t in tools]
