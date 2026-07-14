"""冒烟测试：确认启动骨架可用、组合根装配不报错。

真实单测按层镜像编写(tests/domain、tests/application ...)，
直接对着 domain / application 断言，不触真实 IO。
"""
import unittest

from bootstrap.container import Container, build_container


class BootstrapSmokeTest(unittest.TestCase):
    def test_build_container_returns_container(self) -> None:
        """skip_ai=True 时返回最小容器，无外部依赖。"""
        container = build_container(skip_ai=True)
        self.assertIsInstance(container, Container)

    def test_build_container_without_api_key_graceful(self) -> None:
        """无 API Key 时不抛异常，返回不含 agent_service 的容器。"""
        container = build_container()
        self.assertIsInstance(container, Container)
        # 无 API Key 时 agent_service 为 None
        self.assertIsNone(container.agent_service)

    def test_build_container_skip_ai_has_no_agent(self) -> None:
        """skip_ai=True 时 agent_service 为 None。"""
        container = build_container(skip_ai=True)
        self.assertIsNone(container.agent_service)
        self.assertIsNone(container.llm_factory)
        self.assertEqual(len(container.tools), 0)


if __name__ == "__main__":
    unittest.main()
