"""interfaces/api 路由与 DI provider 测试——手搭最小 app + 鸭子类型桩容器。"""
import unittest
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.skill_config import SkillConfig
from interfaces.api.routes import all_routers


class _StubIdentityRepo:
    def get(self, key: str) -> AgentIdentity:
        return AgentIdentity(persona="测试助手", tones="正式")


class _StubSkillRepo:
    def get(self, key: str) -> list[SkillConfig]:
        return [
            SkillConfig(name="receiving", description="收票", task_instructions="处理收票")
        ]


def _make_app() -> FastAPI:
    app = FastAPI()
    for router in all_routers:
        app.include_router(router)
    app.state.container = SimpleNamespace(
        agent_identity_repo=_StubIdentityRepo(),
        skill_config_repo=_StubSkillRepo(),
    )
    return app


class InterfacesApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(_make_app())

    def test_health(self) -> None:
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_agent_identity(self) -> None:
        resp = self.client.get("/agent/identity")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["persona"], "测试助手")

    def test_agent_skills(self) -> None:
        resp = self.client.get("/agent/skills")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0]["name"], "receiving")


if __name__ == "__main__":
    unittest.main()
