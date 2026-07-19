"""DomainEvent 基类测试——frozen 且自带 occurred_at。"""
from __future__ import annotations

import unittest
from datetime import datetime

from pydantic import ValidationError

from domain.shared.events import DomainEvent


class DomainEventTest(unittest.TestCase):
    def test_has_occurred_at(self) -> None:
        self.assertIsInstance(DomainEvent().occurred_at, datetime)

    def test_frozen(self) -> None:
        ev = DomainEvent()
        with self.assertRaises(ValidationError):
            ev.occurred_at = datetime.now()  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
