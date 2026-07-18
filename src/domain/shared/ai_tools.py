"""AI 工具端口——定义工具契约。

领域层不依赖任何框架（如 LangChain）。
具体工具的语义（做什么）在领域层定义；
工具的 LangChain 包装（怎么做）在基础设施层完成。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """工具执行结果（值对象，不可变）。"""

    success: bool = Field(description="是否成功执行")
    content: str = Field(description="返回给 LLM 的文本内容")
    tool_name: str = Field(description="工具名称")
    error: str | None = Field(default=None, description="失败时的错误信息")

    model_config = {"frozen": True}


class AITool(ABC):
    """AI 工具端口（抽象基类）。

    每一个领域工具需实现此接口，定义：
    - name: LLM 用于识别的工具名称。
    - description: LLM 据此判断何时该调用此工具（这是最重要的字段）。
    - execute: 执行工具逻辑，返回 ToolResult。

    具体工具示例：
        class InvoiceLookupTool(AITool):
            name = "lookup_invoice"
            description = "根据发票号码查询发票详细信息，包括金额、税号、开票日期等。"
            async def execute(self, invoice_id: str) -> ToolResult:
                ...
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称。LLM 用此标识符选择工具。"""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述。LLM 阅读此文本决定何时调用工具。

        建议包含：功能说明、适用场景、参数含义。
        """
        ...

    @abstractmethod
    async def execute(self, **kwargs: str) -> ToolResult:
        """执行工具逻辑。

        Args:
            **kwargs: LLM 传入的参数（字符串键值对），由具体工具自行解析和校验。

        Returns:
            ToolResult: 包含成功/失败状态和返回内容的不可变结果。
        """
        ...
