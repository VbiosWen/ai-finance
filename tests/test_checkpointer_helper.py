"""checkpointer 助手测试——DSN 方言剥离(纯函数,不连库)。"""
from __future__ import annotations

import unittest

from infrastructure.client.checkpointer import to_psycopg_dsn


class ToPsycopgDsnTest(unittest.TestCase):
    def test_strips_asyncpg_driver_suffix(self) -> None:
        self.assertEqual(
            to_psycopg_dsn("postgresql+asyncpg://u:p@127.0.0.1:5432/db"),
            "postgresql://u:p@127.0.0.1:5432/db",
        )

    def test_plain_dsn_unchanged(self) -> None:
        self.assertEqual(
            to_psycopg_dsn("postgresql://u:p@h:5432/db"),
            "postgresql://u:p@h:5432/db",
        )

    def test_no_scheme_unchanged(self) -> None:
        self.assertEqual(to_psycopg_dsn("not-a-dsn"), "not-a-dsn")


if __name__ == "__main__":
    unittest.main()
