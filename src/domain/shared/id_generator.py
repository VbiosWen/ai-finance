"""进程内单调 UUIDv7 生成器（RFC 9562, Method 1）。

纯标准库实现，零第三方依赖——供各子域生成趋势递增的聚合标识。
单调性：同进程严格递增（48 位毫秒时间戳 + rand_a 作 12 位毫秒内计数器）；
时钟回拨时沿用上次时间戳继续计数，计数器打满则借下一毫秒，ID 永不倒退。
不可枚举性：每个 ID 含 62 位安全随机（rand_b）。
"""
from __future__ import annotations

import secrets
import threading
import time
from uuid import UUID

_lock = threading.Lock()
_last_ms = 0
_counter = 0

_MAX_COUNTER = 0xFFF  # 12 位计数器上限：单毫秒 4096 个


def uuid7() -> UUID:
    """生成一个单调递增的 UUIDv7。"""
    global _last_ms, _counter
    with _lock:
        ms = time.time_ns() // 1_000_000
        if ms > _last_ms:
            _last_ms = ms
            _counter = 0
        else:  # 同毫秒并发或时钟回拨：沿用上次时间戳递增计数
            _counter += 1
            if _counter > _MAX_COUNTER:
                _last_ms += 1  # 借下一毫秒
                _counter = 0
        value = (
            (_last_ms & 0xFFFF_FFFF_FFFF) << 80  # unix_ts_ms: bit 80-127
            | 0x7 << 76                          # version 7:  bit 76-79
            | _counter << 64                     # 计数器:     bit 64-75
            | 0b10 << 62                         # variant:    bit 62-63
            | secrets.randbits(62)               # rand_b:     bit 0-61
        )
        return UUID(int=value)
