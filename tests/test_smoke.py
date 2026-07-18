"""冒烟测试：确认启动骨架可用、组合根装配不报错。

真实单测按层镜像编写(tests/domain、tests/application ...)，
直接对着 domain / application 断言，不触真实 IO。
"""
import asyncio
import unittest

from bootstrap.container import Container, build_container


class BootstrapSmokeTest(unittest.TestCase):
    def test_build_container_skip_ai_returns_container(self) -> None:
        """skip_ai=True 时返回最小容器，无外部依赖。"""
        container = asyncio.run(build_container(skip_ai=True))
        self.assertIsInstance(container, Container)

    def test_build_container_skip_ai_has_no_agent(self) -> None:
        """skip_ai=True 时 agent_service 为 None。"""
        container = asyncio.run(build_container(skip_ai=True))
        self.assertIsNone(container.agent_service)
        self.assertIsNone(container.llm_factory)
        self.assertEqual(len(container.tools), 0)

    def test_build_container_without_config_raises(self) -> None:
        """非 skip_ai 模式下不传 config 应抛出 ValueError。"""
        with self.assertRaises(ValueError):
            asyncio.run(build_container())

    def test_build_container_with_config_loads(self) -> None:
        """有 config.json 时正常加载 LLM（需要有效 API Key）。"""
        from pathlib import Path

        from infrastructure.config.llm_config import LLMConfig

        config_path = Path(__file__).parent.parent / "config" / "config.json"
        if not config_path.exists():
            self.skipTest("config.json 不存在")

        config = LLMConfig.load()
        container = asyncio.run(build_container(config=config))
        self.assertIsInstance(container, Container)
        # 有有效 API Key 时 agent_service 不应为 None
        if container.agent_service is None and container.llm_factory is None:
            self.skipTest("API Key 无效或缺失，AI 组件未装配")


if __name__ == "__main__":
    unittest.main()
