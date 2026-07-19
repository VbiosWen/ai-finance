"""Container 构造、不可变性与关闭语义测试——全部零 IO 桩,不触网络/数据库。"""
import asyncio
import unittest
from contextlib import AsyncExitStack

from pydantic import ValidationError

from bootstrap.container import Container
from tests.support import make_stub_container


class ContainerTest(unittest.TestCase):
    def test_construct_with_stubs(self) -> None:
        """零 IO 桩可构造出合法 Container。"""
        container = make_stub_container()
        self.assertIsInstance(container, Container)
        self.assertEqual(container.tools, [])

    def test_frozen(self) -> None:
        """frozen=True:构造后字段不可赋值。"""
        container = make_stub_container()
        with self.assertRaises(ValidationError):
            container.tools = []

    def test_rejects_non_agent_service(self) -> None:
        """agent_service 字段拒绝未实现端口的对象。"""
        base = make_stub_container()
        kwargs = {name: getattr(base, name) for name in Container.model_fields}
        kwargs["agent_service"] = object()
        with self.assertRaises(ValidationError):
            Container(**kwargs)

    def test_shutdown_closes_exit_stack(self) -> None:
        """shutdown() 触发 exit_stack 中注册的关闭回调。"""
        closed: list[str] = []

        async def scenario() -> None:
            stack = AsyncExitStack()

            async def _close() -> None:
                closed.append("closed")

            stack.push_async_callback(_close)
            container = make_stub_container(exit_stack=stack)
            await container.shutdown()

        asyncio.run(scenario())
        self.assertEqual(closed, ["closed"])


if __name__ == "__main__":
    unittest.main()
