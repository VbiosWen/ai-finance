"""NacosClient 单元测试。

需要 Docker 中运行 Nacos 才能通过集成测试。
若 Nacos 不可用，集成测试会自动跳过。
"""
from __future__ import annotations

import asyncio
import json
import unittest


def _nacos_is_available() -> bool:
    """检测本地 Nacos gRPC 端口 9848 是否可达。"""
    import socket

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", 9848))
        return True
    except (OSError, ConnectionRefusedError):
        return False
    finally:
        s.close()


_NACOS_READY: bool = _nacos_is_available()


def _require_nacos(test_method):
    return unittest.skipUnless(_NACOS_READY, "Nacos 未启动，跳过集成测试")(test_method)


# ---------------------------------------------------------------------------
# 纯单元测试（不需要 Nacos 服务）
# ---------------------------------------------------------------------------


class TestNacosConfig(unittest.TestCase):
    """NacosConfig 模型单测。"""

    def test_default_values(self):
        from infrastructure.client.nacos import NacosConfig

        cfg = NacosConfig()
        self.assertEqual(cfg.address, "127.0.0.1:8848")
        self.assertEqual(cfg.namespace, "")

    def test_custom_values(self):
        from infrastructure.client.nacos import NacosConfig

        cfg = NacosConfig(address="nacos.example.com:8848", namespace="prod")
        self.assertEqual(cfg.address, "nacos.example.com:8848")
        self.assertEqual(cfg.namespace, "prod")

    def test_get_client_config(self):
        from infrastructure.client.nacos import NacosConfig

        cfg = NacosConfig(address="10.0.0.1:8848", namespace="test-ns")
        client_cfg = cfg.get_client_config()
        self.assertEqual(client_cfg.server_list, ["10.0.0.1:8848"])
        self.assertEqual(client_cfg.namespace_id, "test-ns")

    def test_frozen_prevents_mutation(self):
        from infrastructure.client.nacos import NacosConfig

        cfg = NacosConfig()
        with self.assertRaises(Exception):
            cfg.address = "other:8848"


class TestNacosClientNoServer(unittest.TestCase):
    """不依赖 Nacos 服务端的纯单元测试。"""

    def setUp(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        self.config = NacosConfig()
        self.client = NacosClient(self.config)

    def test_client_creation_has_no_service(self):
        self.assertIsNone(self.client._nacos_service)

    def test_ensure_started_raises_before_start(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.client._ensure_started()
        self.assertIn("未启动", str(ctx.exception))

    def test_stop_when_not_started_is_noop(self):
        asyncio.run(self.client.stop())
        self.assertIsNone(self.client._nacos_service)


class TestNacosClientErrors(unittest.TestCase):
    """异常场景：未 start 就调用方法应抛出 RuntimeError。"""

    def setUp(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        self.client = NacosClient(NacosConfig())

    def test_get_config_before_start_raises(self):
        with self.assertRaises(RuntimeError):
            asyncio.run(self.client.get_config("test", "group"))


# ---------------------------------------------------------------------------
# 集成测试（需要 Nacos Docker）
# ---------------------------------------------------------------------------


_CONN_PARAMS = {"address": "127.0.0.1:8848", "namespace": "ai-finance"}


@unittest.skipUnless(_NACOS_READY, "Nacos 未启动，跳过集成测试")
class TestNacosClientLifecycle(unittest.TestCase):
    """客户端生命周期测试。"""

    @_require_nacos
    def test_start_and_stop(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        async def _test():
            client = NacosClient(NacosConfig(**_CONN_PARAMS))
            await client.start()
            self.assertIsNotNone(client._nacos_service)
            await client.stop()
            self.assertIsNone(client._nacos_service)

        asyncio.run(_test())

    @_require_nacos
    def test_start_twice_is_idempotent(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        async def _test():
            client = NacosClient(NacosConfig(**_CONN_PARAMS))
            await client.start()
            svc1 = client._nacos_service
            await client.start()
            svc2 = client._nacos_service
            self.assertIs(svc1, svc2)
            await client.stop()

        asyncio.run(_test())

    @_require_nacos
    def test_async_context_manager(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        async def _test():
            async with NacosClient(NacosConfig(**_CONN_PARAMS)) as client:
                self.assertIsNotNone(client._nacos_service)
                raw = await client.get_config("llm-config", group="AI_FINANCE")
                self.assertIsNotNone(raw)

        asyncio.run(_test())


@unittest.skipUnless(_NACOS_READY, "Nacos 未启动，跳过集成测试")
class TestNacosClientRead(unittest.TestCase):
    """配置读取测试。"""

    @_require_nacos
    def test_get_config_existing(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        async def _test():
            async with NacosClient(NacosConfig(**_CONN_PARAMS)) as client:
                raw = await client.get_config("llm-config", group="AI_FINANCE")
                self.assertIsNotNone(raw)
                self.assertIn("model", raw)

        asyncio.run(_test())

    @_require_nacos
    def test_get_json_returns_dict(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        async def _test():
            async with NacosClient(NacosConfig(**_CONN_PARAMS)) as client:
                data = await client.get_json("llm-config", group="AI_FINANCE")
                self.assertIsInstance(data, dict)
                self.assertIn("model", data)

        asyncio.run(_test())

    @_require_nacos
    def test_get_config_nonexistent_returns_none(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig

        async def _test():
            async with NacosClient(NacosConfig(**_CONN_PARAMS)) as client:
                raw = await client.get_config("nonexistent-xyz", group="UNITTEST")
                self.assertIsNone(raw)

        asyncio.run(_test())


# ---------------------------------------------------------------------------
# Repository 集成测试（YAML 解析）
# ---------------------------------------------------------------------------


@unittest.skipUnless(_NACOS_READY, "Nacos 未启动，跳过集成测试")
class TestNacosAgentIdentityRepository(unittest.TestCase):
    """NacosAgentIdentityRepository 集成测试。"""

    @_require_nacos
    def test_load_and_get(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig
        from infrastructure.ports import NacosAgentIdentityRepository

        async def _test():
            async with NacosClient(NacosConfig(**_CONN_PARAMS)) as client:
                repo = NacosAgentIdentityRepository(client)
                await repo.load()
                identity = repo.get("agent-identity")
                self.assertEqual(identity.persona, "资深Java工程师")
                self.assertEqual(len(identity.globals_constraints), 3)

        asyncio.run(_test())


@unittest.skipUnless(_NACOS_READY, "Nacos 未启动，跳过集成测试")
class TestNacosSkillConfigRepository(unittest.TestCase):
    """NacosSkillConfigRepository 集成测试。"""

    @_require_nacos
    def test_load_and_get(self):
        from infrastructure.client.nacos import NacosClient, NacosConfig
        from infrastructure.ports import NacosSkillConfigRepository

        async def _test():
            async with NacosClient(NacosConfig(**_CONN_PARAMS)) as client:
                repo = NacosSkillConfigRepository(client)
                await repo.load()
                skills = repo.get("skill-configs")
                self.assertGreaterEqual(len(skills), 3)
                names = [s.name for s in skills]
                self.assertIn("代码审查", names)
                self.assertIn("单元测试生成", names)
                self.assertIn("性能优化", names)

        asyncio.run(_test())
