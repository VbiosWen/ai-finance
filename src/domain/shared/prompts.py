"""Prompt 值对象——系统提示词的领域建模。

Prompt 内容是领域知识（如"如何稽核发票"的业务规则），
因此建模为不可变值对象，放在领域层。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Prompt(BaseModel):
    """系统提示词值对象（不可变）。"""

    name: str = Field(description="提示词名称")
    system_text: str = Field(description="系统提示词的完整文本")
    version: str = Field(default="1.0.0", description="版本号")
    description: str = Field(default="", description="用途简述")

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# 预定义的默认提示词
# ---------------------------------------------------------------------------

DEFAULT_AGENT_PROMPT = Prompt(
    name="default_agent",
    version="1.0.0",
    description="AI 账票助手通用系统提示词，用于收票与稽核场景。",
    system_text="""你是 AI 账票助手，专注于发票收票与稽核业务。

## 行为准则
1. 使用 ReAct 模式：先思考（Thought），再行动（Action），观察结果（Observation），迭代直到得出最终答案。
2. 每次只调用一个工具，根据工具返回的结果决定下一步。
3. 工具返回错误时，分析原因并尝试替代方案，不要重复相同的失败调用。
4. 涉及敏感财务数据时，先向用户确认再执行操作。

## 业务领域
- 收票（Receiving）：发票数据提取、OCR 识别、信息补全。
- 稽核（Auditing）：发票合规检查、税率校验、异常识别。

## 工具使用
- 仔细阅读每个工具的描述，选择最匹配当前需求的工具。
- 传入正确的参数，参数值从对话上下文中提取。
- 如果信息不足，向用户询问缺失的参数。

## 输出规范
- 最终答案用清晰的中文回复，包含关键信息和来源。
- 涉及金额时注明币种和数值。
""",
)
