"""get_agent_service DI 测试——从 app.state 取单例，缺失时 503。"""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from fastapi import HTTPException

from interfaces.api.dependencies import get_agent_service


def _fake_request(agent_service: object | None) -> object:
    """构造一个仅含 app.state.container.agent_service 的假 Request。"""
    container = SimpleNamespace()
    if agent_service is not None:
        container.agent_service = agent_service
    state = SimpleNamespace(container=container)
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


class GetAgentServiceTest(unittest.TestCase):
    def test_returns_singleton(self) -> None:
        sentinel = object()
        result = get_agent_service(_fake_request(sentinel))
        self.assertIs(result, sentinel)

    def test_missing_raises_503(self) -> None:
        with self.assertRaises(HTTPException) as ctx:
            get_agent_service(_fake_request(None))
        self.assertEqual(ctx.exception.status_code, 503)


if __name__ == "__main__":
    unittest.main()
