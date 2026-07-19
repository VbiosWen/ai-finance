"""AgentService 端口的 runtime_checkable 校验测试。"""
import unittest

from application.dto.agent_dto import AgentRequest, AgentResponse
from application.ports.agent_service import AgentService


class _StubAgentService:
    async def run(self, request: AgentRequest) -> AgentResponse:
        return AgentResponse(reply="stub")

    async def stream(self, request: AgentRequest):
        yield


class AgentServicePortTest(unittest.TestCase):
    def test_isinstance_accepts_structural_implementation(self) -> None:
        """runtime_checkable 后,结构性实现应通过 isinstance 检查。"""
        self.assertIsInstance(_StubAgentService(), AgentService)

    def test_isinstance_rejects_non_implementation(self) -> None:
        """未实现 run/stream 的对象不通过 isinstance 检查。"""
        self.assertNotIsInstance(object(), AgentService)


if __name__ == "__main__":
    unittest.main()
