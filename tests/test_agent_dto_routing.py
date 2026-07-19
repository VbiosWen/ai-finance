"""Agent DTO 路由扩展测试——routing 事件与 routed_skill 字段。"""
from __future__ import annotations

import json
import unittest

from application.dto.agent_dto import AgentResponse, AgentStreamEvent


class RoutingEventTest(unittest.TestCase):
    def test_routing_event_type_and_skill_name(self) -> None:
        evt = AgentStreamEvent(event_type="routing", content="识别意图：稽核", skill_name="auditing")
        self.assertEqual(evt.event_type, "routing")
        self.assertEqual(evt.skill_name, "auditing")

    def test_routing_event_json_contains_skill_name(self) -> None:
        evt = AgentStreamEvent(event_type="routing", skill_name="general", content="转通用助手")
        parsed = json.loads(evt.model_dump_json())
        self.assertEqual(parsed["skill_name"], "general")

    def test_token_event_skill_name_defaults_none(self) -> None:
        evt = AgentStreamEvent(event_type="token", content="x")
        self.assertIsNone(evt.skill_name)


class RoutedSkillTest(unittest.TestCase):
    def test_response_routed_skill(self) -> None:
        resp = AgentResponse(reply="ok", routed_skill="auditing")
        self.assertEqual(resp.routed_skill, "auditing")

    def test_response_routed_skill_defaults_none(self) -> None:
        self.assertIsNone(AgentResponse(reply="ok").routed_skill)


if __name__ == "__main__":
    unittest.main()
