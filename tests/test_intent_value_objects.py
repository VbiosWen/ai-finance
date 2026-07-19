"""意图/路由值对象测试——字段校验与不可变性。"""
from __future__ import annotations

import unittest

from pydantic import ValidationError

from domain.value_objects.intent import IntentClassification, RoutingDecision
from domain.value_objects.routing_config import RoutingConfig


class IntentClassificationTest(unittest.TestCase):
    def test_defaults(self) -> None:
        c = IntentClassification(confidence=0.5)
        self.assertIsNone(c.target_skill)
        self.assertEqual(c.reason, "")

    def test_confidence_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            IntentClassification(confidence=1.5)
        with self.assertRaises(ValidationError):
            IntentClassification(confidence=-0.1)

    def test_frozen(self) -> None:
        c = IntentClassification(confidence=0.5)
        with self.assertRaises(ValidationError):
            c.confidence = 0.9  # type: ignore[misc]


class RoutingDecisionTest(unittest.TestCase):
    def test_fields(self) -> None:
        d = RoutingDecision(skill_name="auditing")
        self.assertEqual(d.skill_name, "auditing")
        self.assertFalse(d.is_fallback)


class RoutingConfigTest(unittest.TestCase):
    def test_defaults(self) -> None:
        cfg = RoutingConfig()
        self.assertEqual(cfg.confidence_threshold, 0.6)
        self.assertEqual(cfg.fallback_skill_name, "general")

    def test_threshold_bounds(self) -> None:
        with self.assertRaises(ValidationError):
            RoutingConfig(confidence_threshold=2.0)


if __name__ == "__main__":
    unittest.main()
