"""RoutingPolicy 领域服务测试——纯函数裁决，无 mock。"""
from __future__ import annotations

import unittest

from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig


class RoutingPolicyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = RoutingPolicy(RoutingConfig(confidence_threshold=0.6, fallback_skill_name="general"))
        self.available = {"auditing", "receiving", "general"}

    def test_high_confidence_hit(self) -> None:
        c = IntentClassification(target_skill="auditing", confidence=0.9)
        d = self.policy.decide(c, self.available)
        self.assertEqual(d.skill_name, "auditing")
        self.assertFalse(d.is_fallback)

    def test_low_confidence_falls_back(self) -> None:
        c = IntentClassification(target_skill="auditing", confidence=0.3)
        d = self.policy.decide(c, self.available)
        self.assertEqual(d.skill_name, "general")
        self.assertTrue(d.is_fallback)

    def test_none_target_falls_back(self) -> None:
        c = IntentClassification(target_skill=None, confidence=0.95)
        d = self.policy.decide(c, self.available)
        self.assertTrue(d.is_fallback)

    def test_target_not_available_falls_back(self) -> None:
        c = IntentClassification(target_skill="unknown_skill", confidence=0.95)
        d = self.policy.decide(c, self.available)
        self.assertEqual(d.skill_name, "general")
        self.assertTrue(d.is_fallback)

    def test_fallback_name_property(self) -> None:
        self.assertEqual(self.policy.fallback_name, "general")


if __name__ == "__main__":
    unittest.main()
