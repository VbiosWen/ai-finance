"""ReAct Agent 工厂——基于 LangChain create_agent 组装 Agent。

LangChain 1.3.13 中 create_react_agent（langgraph.prebuilt）已废弃，
当前标准 API 是 from langchain.agents import create_agent。
"""
from __future__ import annotations

import logging
from typing import Any

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver

logger = logging.getLogger("ai-finance")


def create_react_agent(
    llm: Any,
    tools: list[Any],
    system_prompt: str,
    *,
    checkpointer: Any | None = None,
    enable_memory: bool = True,
) -> Any:
    """创建 ReAct Agent。

    使用 LangChain 的 create_agent API，底层基于 LangGraph StateGraph，
    自动装配 Agent 节点、Tools 节点、条件路由和 ReAct 循环逻辑。

    Args:
        llm: LangChain BaseChatModel 实例（ChatOpenAI / ChatAnthropic 等）。
        tools: LangChain Tool 列表（通过 tool_adapter 从领域工具转换而来）。
        system_prompt: 系统提示词文本。
        checkpointer: 检查点存储器，默认使用内存实现（MemorySaver）。
        enable_memory: 是否启用对话记忆（基于 thread_id 的多轮对话）。

    Returns:
        编译后的 LangGraph agent 图，可直接调用 .ainvoke() / .astream_events()。
    """
    if checkpointer is None and enable_memory:
        checkpointer = MemorySaver()

    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_prompt,
        checkpointer=checkpointer,
    )

    logger.info(
        "ReAct Agent 创建完成。LLM=%s, 工具数=%d, 记忆=%s",
        type(llm).__name__,
        len(tools),
        "已启用" if enable_memory else "未启用",
    )
    return agent
