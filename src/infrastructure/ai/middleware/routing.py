"""路由中间件——意图识别与技能裁决进图,决策随 checkpoint 留痕。

RoutingState 是 LangGraph 状态 schema,框架契约要求 TypedDict
(项目「兼容第三方库」例外);业务值对象仍一律 Pydantic。
"""
from __future__ import annotations

import logging

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import AgentState
from langchain_core.messages import AIMessage, HumanMessage
from typing_extensions import NotRequired

from application.ports.intent_recognizer import IntentRecognizer
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.agent_prompt_config import AgentPromptConfig
from domain.value_objects.skill_config import SkillConfig

logger = logging.getLogger("ai-finance")


class RoutingState(AgentState):
    """图状态扩展:路由决策通道(随 checkpointer 持久化)。"""

    routed_skill: NotRequired[str]
    routing_confidence: NotRequired[float]
    routing_fallback: NotRequired[bool]


def _to_dict_messages(messages: list, limit: int) -> list[dict[str, str]]:
    """LangChain 消息 → recognizer 的 dict 格式。

    只保留 user/assistant 的非空文本(System/Tool 对意图识别无增益),裁尾部 limit 条。
    """
    dicts: list[dict[str, str]] = []
    for m in messages:
        if isinstance(m, HumanMessage):
            role = "user"
        elif isinstance(m, AIMessage):
            role = "assistant"
        else:
            continue
        if isinstance(m.content, str) and m.content:
            dicts.append({"role": role, "content": m.content})
    return dicts[-limit:]


class RoutingMiddleware(AgentMiddleware):
    """每轮识别意图并裁决技能;每次模型调用按裁决动态换技能 prompt。"""

    state_schema = RoutingState

    def __init__(
        self,
        *,
        recognizer: IntentRecognizer,
        policy: RoutingPolicy,
        identity: AgentIdentity,
        skills: list[SkillConfig],
        general_skill: SkillConfig,
        recognizer_window: int = 8,
    ) -> None:
        super().__init__()
        self._recognizer = recognizer
        self._policy = policy
        self._window = recognizer_window
        catalog = [*skills, general_skill]
        self._catalog = catalog
        self._available = {s.name for s in catalog}
        # 技能 prompt 启动期一次渲染(AgentPromptConfig 不可变)
        self._prompts = {
            s.name: AgentPromptConfig(agent_identity=identity, skill=[s]).render()
            for s in catalog
        }

    # ── 每轮一次:意图识别 + 裁决(checkpointer 已回放全史) ──────────
    async def abefore_agent(self, state, runtime):
        history = _to_dict_messages(state["messages"], self._window)
        try:
            cls = await self._recognizer.recognize(history, self._catalog)
        except Exception as exc:  # 识别失败 → 安全降级,绝不让路由搞垮对话
            logger.warning("意图识别失败,降级兜底: %s", exc)
            return {
                "routed_skill": self._policy.fallback_name,
                "routing_confidence": 0.0,
                "routing_fallback": True,
            }
        dec = self._policy.decide(cls, self._available)
        logger.info(
            "路由裁决: target=%s confidence=%.2f → skill=%s fallback=%s reason=%s",
            cls.target_skill, cls.confidence, dec.skill_name, dec.is_fallback, cls.reason,
        )
        return {
            "routed_skill": dec.skill_name,
            "routing_confidence": cls.confidence,
            "routing_fallback": dec.is_fallback,
        }

    # ── 每次模型调用:按裁决换技能 prompt ────────────────────────────
    def prompt_for(self, skill_name: str | None) -> str:
        """按技能名取渲染好的 system prompt;未裁决/未知技能 → 兜底技能。"""
        fallback = self._policy.fallback_name
        return self._prompts.get(skill_name or fallback, self._prompts[fallback])

    async def awrap_model_call(self, request, handler):
        request = request.override(
            system_prompt=self.prompt_for(request.state.get("routed_skill"))
        )
        return await handler(request)
