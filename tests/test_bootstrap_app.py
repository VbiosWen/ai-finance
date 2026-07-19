"""create_app 工厂 + lifespan + 路由端到端测试(预制桩容器,零 IO)。"""
import unittest
from contextlib import AsyncExitStack

from fastapi.testclient import TestClient

from bootstrap.app import create_app
from tests.support import make_stub_container


class BootstrapAppTest(unittest.TestCase):
    def test_health_and_agent_routes(self) -> None:
        """三个保留路由行为与重构前一致。"""
        with TestClient(create_app(make_stub_container())) as client:
            self.assertEqual(client.get("/health").json(), {"status": "ok"})
            self.assertEqual(
                client.get("/agent/identity").json()["persona"], "测试助手"
            )
            skills = client.get("/agent/skills").json()
            self.assertEqual(skills[0]["name"], "receiving")

    def test_config_endpoint_removed(self) -> None:
        """/config/{data_id} 已移除(安全)。"""
        with TestClient(create_app(make_stub_container())) as client:
            self.assertEqual(client.get("/config/llm-config").status_code, 404)

    def test_prebuilt_container_not_shutdown_by_lifespan(self) -> None:
        """预制容器由调用方管理生命周期,lifespan 退出不触发 shutdown。"""
        closed: list[str] = []
        stack = AsyncExitStack()

        async def _close() -> None:
            closed.append("closed")

        stack.push_async_callback(_close)
        with TestClient(create_app(make_stub_container(exit_stack=stack))):
            pass
        self.assertEqual(closed, [])


if __name__ == "__main__":
    unittest.main()
