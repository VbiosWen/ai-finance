"""工具适配器测试——验证 AITool → LangChain Tool 转换逻辑。"""
from __future__ import annotations

import json
import unittest

from domain.shared.ai_tools import AITool, ToolResult
from infrastructure.ai.tool_adapter import adapt_ai_tool, adapt_ai_tools


class _GreetTool(AITool):
    """测试用工具：打招呼。"""
    name = "greet"
    description = "向用户打招呼。参数: name (姓名)"

    async def execute(self, **kwargs: str) -> ToolResult:
        name = kwargs.get("name", "世界")
        return ToolResult(
            success=True,
            content=f"你好, {name}!",
            tool_name="greet",
        )


class _FailingTool(AITool):
    """测试用工具：必定失败。"""
    name = "failer"
    description = "无论如何都失败的工具。"

    async def execute(self, **kwargs: str) -> ToolResult:
        return ToolResult(
            success=False,
            content="",
            tool_name="failer",
            error="故意失败用于测试",
        )


class _ExceptionTool(AITool):
    """测试用工具：抛出异常。"""
    name = "exploder"
    description = "执行时抛出异常。"

    async def execute(self, **kwargs: str) -> ToolResult:
        raise RuntimeError("boom!")


class ToolAdapterTest(unittest.IsolatedAsyncioTestCase):
    """工具适配器测试。

    适配器生成的 LangChain StructuredTool 接受单个 `input: str` 参数，
    内部解析 JSON 键值对后调用 AITool.execute(**params)。
    """

    async def test_adapt_single_tool_success(self) -> None:
        """适配后的工具接收 JSON input 字符串，成功执行。"""
        lc_tool = adapt_ai_tool(_GreetTool())
        result = await lc_tool.ainvoke({"input": json.dumps({"name": "小明"})})
        self.assertIn("小明", result)
        self.assertIn("你好", result)

    async def test_adapt_single_tool_default_args(self) -> None:
        """无 input 时使用默认参数。"""
        lc_tool = adapt_ai_tool(_GreetTool())
        result = await lc_tool.ainvoke({})
        self.assertIn("世界", result)

    async def test_adapt_tool_with_json_string_input(self) -> None:
        """JSON 字符串作为 input。"""
        lc_tool = adapt_ai_tool(_GreetTool())
        result = await lc_tool.ainvoke(
            {"input": json.dumps({"name": "小红"})}
        )
        self.assertIn("小红", result)

    async def test_adapt_tool_plain_string_input(self) -> None:
        """普通字符串作为 input（非 JSON），整体作为 query 参数。"""
        lc_tool = adapt_ai_tool(_GreetTool())
        result = await lc_tool.ainvoke({"input": "你好世界"})
        # 非 JSON 输入，整体作为 query 参数传入，不匹配 name 参数，
        # 所以使用默认值"世界"
        self.assertIn("你好", result)

    async def test_adapt_tool_failure(self) -> None:
        """工具返回失败状态时，适配器返回错误描述文本。"""
        lc_tool = adapt_ai_tool(_FailingTool())
        result = await lc_tool.ainvoke({"input": "{}"})
        self.assertIn("故意失败", result)

    async def test_adapt_tool_exception(self) -> None:
        """工具抛出异常时，适配器捕获并返回异常文本。"""
        lc_tool = adapt_ai_tool(_ExceptionTool())
        result = await lc_tool.ainvoke({"input": "{}"})
        self.assertIn("boom", result)

    def test_adapt_tools_batch(self) -> None:
        """批量适配返回等量工具列表。"""
        tools = [_GreetTool(), _FailingTool()]
        result = adapt_ai_tools(tools)
        self.assertEqual(len(result), 2)

    def test_adapt_tool_has_name_and_description(self) -> None:
        """适配后的 LangChain Tool 保留名称和描述。"""
        lc_tool = adapt_ai_tool(_GreetTool())
        self.assertEqual(lc_tool.name, "greet")
        self.assertIn("打招呼", lc_tool.description)


if __name__ == "__main__":
    unittest.main()
