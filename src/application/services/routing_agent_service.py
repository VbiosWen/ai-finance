"""路由 Agent 服务 —— 实现 AgentService 端口，内敛路由复杂度。

编排：意图识别 → RoutingPolicy 裁决 → 分发到选中的技能/兜底 Agent。
识别任一环节失败都安全降级兜底，绝不让路由失败演变成整通对话失败。
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from application.dto.agent_dto import AgentRequest, AgentResponse, AgentStreamEvent
from application.ports.agent_service import AgentService
from application.ports.intent_recognizer import IntentRecognizer
from application.services.agent_registry import AgentRegistry
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.intent import RoutingDecision

logger = logging.getLogger("ai-finance")


def _routing_message(dec: RoutingDecision) -> str:
    if dec.is_fallback:
        return "未匹配专业技能，转通用助手"
    return f"识别意图：{dec.skill_name}"


class RoutingAgentService:
    """实现 AgentService 端口（run / stream）。"""

    def __init__(
        self,
        recognizer: IntentRecognizer,
        policy: RoutingPolicy,
        registry: AgentRegistry,
    ) -> None:
        self._recognizer = recognizer
        self._policy = policy
        self._registry = registry

    async def _route(self, req: AgentRequest) -> RoutingDecision:
        catalog = self._registry.catalog()
        try:
            cls = await self._recognizer.recognize(req.messages, catalog)
        except Exception as exc:  # 识别失败 → 安全降级
            logger.warning("意图识别失败，降级兜底: %s", exc)
            return RoutingDecision(skill_name=self._policy.fallback_name, is_fallback=True)
        dec = self._policy.decide(cls, self._registry.available())
        logger.info(
            "路由裁决: target=%s confidence=%.2f → skill=%s fallback=%s reason=%s",
            cls.target_skill, cls.confidence, dec.skill_name, dec.is_fallback, cls.reason,
        )
        return dec

    async def run(self, req: AgentRequest) -> AgentResponse:
        dec = await self._route(req)
        resp = await self._registry.get(dec.skill_name).run(req)
        return resp.model_copy(update={"routed_skill": dec.skill_name})

    async def stream(self, req: AgentRequest) -> AsyncIterator[AgentStreamEvent]:
        dec = await self._route(req)
        yield AgentStreamEvent(
            event_type="routing",
            skill_name=dec.skill_name,
            content=_routing_message(dec),
        )
        async for ev in self._registry.get(dec.skill_name).stream(req):
            yield ev
