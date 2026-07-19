"""单调 uuid7 生成器测试——格式、位段、严格递增、并发唯一、回拨不倒退。"""
from __future__ import annotations

import threading
import time
import unittest
from uuid import RFC_4122

from domain.shared.id_generator import uuid7


class IdGeneratorTest(unittest.TestCase):
    def test_hex_format(self) -> None:
        self.assertRegex(uuid7().hex, r"^[0-9a-f]{32}$")

    def test_version_and_variant(self) -> None:
        u = uuid7()
        self.assertEqual(u.version, 7)
        self.assertEqual(u.variant, RFC_4122)

    def test_strictly_increasing_sequence(self) -> None:
        ids = [uuid7() for _ in range(5000)]
        for a, b in zip(ids, ids[1:]):
            self.assertLess(a.int, b.int)

    def test_hex_sort_order_matches_generation_order(self) -> None:
        hexes = [uuid7().hex for _ in range(5000)]
        self.assertEqual(hexes, sorted(hexes))

    def test_threaded_generation_unique_and_ordered(self) -> None:
        buckets: list[list[int]] = [[] for _ in range(8)]

        def worker(bucket: list[int]) -> None:
            for _ in range(2000):
                bucket.append(uuid7().int)

        threads = [threading.Thread(target=worker, args=(b,)) for b in buckets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        flat = [x for b in buckets for x in b]
        self.assertEqual(len(flat), len(set(flat)))  # 跨线程全局无重复
        for b in buckets:
            self.assertEqual(b, sorted(b))  # 各线程内严格递增

    def test_clock_rollback_and_counter_overflow_never_regress(self) -> None:
        # 把生成器状态拨到未来 10 秒，模拟时钟回拨；连续生成压满计数器走借毫秒路径。
        from domain.shared import id_generator as gen

        saved = (gen._last_ms, gen._counter)
        future_ms = time.time_ns() // 1_000_000 + 10_000
        gen._last_ms, gen._counter = future_ms, 0
        try:
            ids = [uuid7() for _ in range(5000)]
            for a, b in zip(ids, ids[1:]):
                self.assertLess(a.int, b.int)          # 永不倒退
            self.assertGreaterEqual(ids[0].int >> 80, future_ms)  # 时间戳段沿用未来值
        finally:
            gen._last_ms, gen._counter = saved


if __name__ == "__main__":
    unittest.main()
