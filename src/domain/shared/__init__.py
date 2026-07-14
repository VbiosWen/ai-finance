"""领域共享模块——跨业务模块的通用领域概念。

导出：
- AITool / ToolResult: AI 工具端口与值对象
- Prompt: 系统提示词值对象
- DEFAULT_AGENT_PROMPT: 默认 AI 账票助手提示词
"""
from domain.shared.ai_tools import AITool, ToolResult
from domain.shared.prompts import DEFAULT_AGENT_PROMPT, Prompt

__all__ = [
    "AITool",
    "DEFAULT_AGENT_PROMPT",
    "Prompt",
    "ToolResult",
]
