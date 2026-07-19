"""ContextWindowPolicy 测试——最近 N 条裁剪。"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from domain.conversation.context_window import ContextWindowPolicy
from domain.conversation.value_objects import Message, MessageRole


def _msgs(n: int) -> tuple[Message, ...]:
    now = datetime.now(timezone.utc)
    return tuple(
        Message(role=MessageRole.USER, content=str(i), created_at=now) for i in range(n)
    )


class ContextWindowPolicyTest(unittest.TestCase):
    def test_selects_last_n(self) -> None:
        selected = ContextWindowPolicy(size=3).select(_msgs(10))
        self.assertEqual([m.content for m in selected], ["7", "8", "9"])

    def test_fewer_than_size_returns_all(self) -> None:
        self.assertEqual(len(ContextWindowPolicy(size=20).select(_msgs(2))), 2)

    def test_non_positive_size_returns_all(self) -> None:
        self.assertEqual(len(ContextWindowPolicy(size=0).select(_msgs(5))), 5)


if __name__ == "__main__":
    unittest.main()
