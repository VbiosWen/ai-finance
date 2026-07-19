"""工具注册表——全局 AITool 实例池。

启动时注册所有业务工具，运行时按名称解析，供 SkillAgentFactory
为每个 Skill 动态装配专属工具链。
"""

from __future__ import annotations

from domain.shared.ai_tools import AITool


class ToolRegistry:
    """全局工具注册表。

    以工具名称（AITool.name）为键存储所有可用工具实例。
    SkillAgentFactory 根据 SkillConfig.tool_names 从此注册表解析工具。

    用法::

        registry = ToolRegistry()
        registry.register(InvoiceLookupTool(db))
        registry.register(ValidateInvoiceTool())

        tools = registry.resolve(["lookup_invoice", "validate_invoice"])
    """

    def __init__(self) -> None:
        self._tools: dict[str, AITool] = {}

    def register(self, tool: AITool) -> None:
        """注册一个工具实例。

        Args:
            tool: 实现了 AITool 端口的工具实例。

        Raises:
            ValueError: 同名工具已注册。
        """
        if tool.name in self._tools:
            raise ValueError(f"工具 '{tool.name}' 已注册，不允许重复")
        self._tools[tool.name] = tool

    def resolve(self, names: list[str]) -> list[AITool]:
        """按名称列表解析工具实例。

        Args:
            names: 工具名称列表。

        Returns:
            AITool 实例列表，顺序与输入一致。

        Raises:
            KeyError: 有名称未在注册表中找到。
        """
        missing = [n for n in names if n not in self._tools]
        if missing:
            raise KeyError(f"工具未注册: {missing}")
        return [self._tools[n] for n in names]

    @property
    def all(self) -> list[AITool]:
        """返回所有已注册的工具。"""
        return list(self._tools.values())

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
