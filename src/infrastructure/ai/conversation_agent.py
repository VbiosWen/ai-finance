"""对话 Agent 单图装配——路由/压缩中间件管道 + checkpointer 记忆。"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware

from application.ports.intent_recognizer import IntentRecognizer
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.middleware.routing import RoutingMiddleware

logger = logging.getLogger("ai-finance")


def build_conversation_agent(
    *,
    llm: Any,
    identity: AgentIdentity,
    skills: list[SkillConfig],
    general_skill: SkillConfig,
    recognizer: IntentRecognizer,
    policy: RoutingPolicy,
    checkpointer: Any | None = None,
    context_middleware: Sequence[AgentMiddleware] = (),
) -> Any:
    """装配单一对话 Agent 图。

    中间件顺位固定:RoutingMiddleware 最先(先裁决,后续压缩/执行都可依赖决策);
    context_middleware 是上下文工程插槽(压缩/规划),按传入顺序执行。
    checkpointer=None 时无记忆(测试/一次性调用);多轮记忆按
    config.configurable.thread_id(= conversation_id)组织。
    """
    routing = RoutingMiddleware(
        recognizer=recognizer,
        policy=policy,
        identity=identity,
        skills=skills,
        general_skill=general_skill,
    )
    agent = create_agent(
        model=llm,
        tools=[],
        # 兜底 prompt;实际每次模型调用都被 awrap_model_call 按裁决覆盖
        system_prompt=routing.prompt_for(None),
        middleware=[routing, *context_middleware],
        checkpointer=checkpointer,
    )
    logger.info(
        "对话 Agent 图装配完成:技能 %d(含兜底 %s),上下文中间件 %d,记忆=%s",
        len(skills) + 1,
        general_skill.name,
        len(context_middleware),
        "checkpointer" if checkpointer is not None else "无",
    )
    return agent
