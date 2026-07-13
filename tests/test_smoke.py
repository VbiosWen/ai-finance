"""冒烟测试:确认启动骨架可用、组合根装配不报错。

真实单测按层镜像编写(tests/domain、tests/application ...),
直接对着 domain / application 断言,不触真实 IO。
"""
import unittest

from bootstrap.container import Container, build_container


class BootstrapSmokeTest(unittest.TestCase):
    def test_build_container_returns_container(self) -> None:
        container = build_container()
        self.assertIsInstance(container, Container)


if __name__ == "__main__":
    unittest.main()
