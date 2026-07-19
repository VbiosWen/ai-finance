"""Agent 数据传输对象（DTO）。

使用 Pydantic v2 定义 agent 调用的输入输出模型,
仅限 application 和 interfaces 层使用，不得泄漏到 domain。
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    """Agent 调用请求。

    Attributes:
        messages: 对话消息列表，每条含 role 和 content。
        thread_id: 对话线程 ID，用于多轮对话记忆。不传则每次独立。
    """

    messages: list[dict[str, str]] = Field(
        default_factory=list,
        description="对话消息列表，格式: [{'role': 'user'|'assistant', 'content': '...'}]",
    )
    thread_id: str | None = Field(
        default=None,
        description="对话线程 ID，传入可恢复之前的对话上下文",
    )


class AgentResponse(BaseModel):
    """Agent 非流式响应。

    Attributes:
        reply: Agent 的最终回复文本。
        thread_id: 关联的对话线程 ID。
        tool_calls_count: 本次请求中工具调用次数。
    """

    reply: str = Field(description="Agent 的最终回复文本")
    thread_id: str | None = Field(default=None, description="对话线程 ID")
    tool_calls_count: int = Field(default=0, description="工具调用次数")
    routed_skill: str | None = Field(
        default=None, description="本次路由命中的技能名（动态路由时回填，可观测）"
    )


class AgentStreamEvent(BaseModel):
    """Agent 流式事件。

    支持六种事件类型：
    - token: LLM 输出的增量文本片段。
    - tool_start: 工具开始执行。
    - tool_end: 工具执行完成。
    - done: 对话结束。
    - error: 发生错误。
    - routing: 对话路由，本轮转接到的技能。
    """

    event_type: Literal["token", "tool_start", "tool_end", "done", "error", "routing"] = Field(
        description="事件类型"
    )
    content: str = Field(default="", description="事件内容")
    tool_name: str | None = Field(default=None, description="工具名称（tool_start/tool_end 时有效）")
    skill_name: str | None = Field(
        default=None, description="路由命中的技能名（仅 routing 事件有值）"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="事件时间戳（UTC）",
    )
