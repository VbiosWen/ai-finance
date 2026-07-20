"""AgentService 测试——验证 LangChainAgentService 的消息转换与适配逻辑。"""
from __future__ import annotations

import asyncio
import unittest

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from application.dto.agent_dto import AgentRequest
from domain.services.routing_policy import RoutingPolicy
from domain.value_objects.agent_identity import AgentIdentity
from domain.value_objects.intent import IntentClassification
from domain.value_objects.routing_config import RoutingConfig
from domain.value_objects.skill_config import SkillConfig
from infrastructure.ai.conversation_agent import build_conversation_agent
from infrastructure.ai.react_agent import (
    LangChainAgentService,
    _build_config,
    _count_tool_calls,
    _extract_last_ai_content,
    _map_event,
    _safe_content,
    _to_langchain_messages,
)


class MessageConversionTest(unittest.TestCase):
    """消息格式转换测试。"""

    def test_user_message(self) -> None:
        """user role 转为 HumanMessage。"""
        result = _to_langchain_messages([{"role": "user", "content": "hello"}])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], HumanMessage)
        self.assertEqual(result[0].content, "hello")

    def test_assistant_message(self) -> None:
        """assistant role 转为 AIMessage。"""
        result = _to_langchain_messages([{"role": "assistant", "content": "hi"}])
        self.assertEqual(len(result), 1)
        self.assertIsInstance(result[0], AIMessage)
        self.assertEqual(result[0].content, "hi")

    def test_multiple_messages(self) -> None:
        """多条消息正确转换。"""
        msgs = [
            {"role": "user", "content": "查询 INV-001"},
            {"role": "assistant", "content": "正在查找..."},
        ]
        result = _to_langchain_messages(msgs)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], HumanMessage)
        self.assertIsInstance(result[1], AIMessage)

    def test_missing_role_defaults_to_user(self) -> None:
        """缺失 role 字段时默认为 user。"""
        result = _to_langchain_messages([{"content": "hello"}])
        self.assertIsInstance(result[0], HumanMessage)

    def test_empty_messages(self) -> None:
        """空消息列表返回空列表。"""
        result = _to_langchain_messages([])
        self.assertEqual(len(result), 0)


class BuildConfigTest(unittest.TestCase):
    """配置构建测试。"""

    def test_with_thread_id(self) -> None:
        """带 thread_id 时构建正确配置。"""
        config = _build_config("thread-42")
        self.assertEqual(config["configurable"]["thread_id"], "thread-42")

    def test_without_thread_id(self) -> None:
        """无 thread_id 时返回空配置。"""
        config = _build_config(None)
        self.assertEqual(config, {})


class ExtractLastAIContentTest(unittest.TestCase):
    """最后 AI 消息提取测试。"""

    def test_single_ai_message(self) -> None:
        """单条 AI 消息被正确提取。"""
        msgs = [AIMessage(content="最终答案")]
        self.assertEqual(_extract_last_ai_content(msgs), "最终答案")

    def test_mixed_messages(self) -> None:
        """混合消息中提取最后一条 AI 内容。"""
        msgs = [
            HumanMessage(content="问题"),
            AIMessage(content="思考中..."),
            AIMessage(content="最终决定"),
            HumanMessage(content="追加问题"),
        ]
        # 最后一条 AI 是 "最终决定"
        self.assertEqual(_extract_last_ai_content(msgs), "最终决定")

    def test_no_ai_message(self) -> None:
        """无 AI 消息时返回空字符串。"""
        msgs = [HumanMessage(content="hello")]
        self.assertEqual(_extract_last_ai_content(msgs), "")


class CountToolCallsTest(unittest.TestCase):
    """工具调用计数测试。"""

    def test_no_tool_calls(self) -> None:
        """无工具调用时返回 0。"""
        msgs = [AIMessage(content="hello")]
        self.assertEqual(_count_tool_calls(msgs), 0)

    def test_empty_messages(self) -> None:
        """空消息列表返回 0。"""
        self.assertEqual(_count_tool_calls([]), 0)


class SafeContentTest(unittest.TestCase):
    """安全提取消息内容测试。"""

    def test_string_content(self) -> None:
        """纯文本内容直接返回。"""
        msg = AIMessage(content="text")
        self.assertEqual(_safe_content(msg), "text")

    def test_multimodal_content(self) -> None:
        """多模态内容拼接文本片段。"""
        msg = AIMessage(content=[
            {"type": "text", "text": "part1"},
            {"type": "text", "text": "part2"},
        ])
        self.assertEqual(_safe_content(msg), "part1part2")

    def test_non_string_content(self) -> None:
        """非字符串非列表内容安全返回字符串形式。"""

        class WeirdContent(dict):
            pass

        msg = WeirdContent()
        msg.content = 42
        self.assertEqual(_safe_content(msg), "42")


class RoutingEventMapTest(unittest.TestCase):
    """routing SSE 帧——从 RoutingMiddleware.before_agent 的 on_chain_end 映射。"""

    def test_maps_routing_decision(self) -> None:
        ev = _map_event({
            "event": "on_chain_end",
            "name": "RoutingMiddleware.before_agent",
            "data": {"output": {"routed_skill": "receiving", "routing_fallback": False}},
        })
        self.assertEqual(ev.event_type, "routing")
        self.assertEqual(ev.skill_name, "receiving")
        self.assertEqual(ev.content, "识别意图：receiving")

    def test_fallback_message(self) -> None:
        ev = _map_event({
            "event": "on_chain_end",
            "name": "RoutingMiddleware.before_agent",
            "data": {"output": {"routed_skill": "general", "routing_fallback": True}},
        })
        self.assertEqual(ev.content, "未匹配专业技能，转通用助手")

    def test_other_chain_end_not_routing(self) -> None:
        self.assertIsNone(_map_event({
            "event": "on_chain_end", "name": "model", "data": {"output": {}},
        }))


class RunRoutedSkillTest(unittest.TestCase):
    """run() 从图终态回填 routed_skill(替代已退役的应用层回填)。"""

    def test_run_returns_routed_skill(self) -> None:
        class _FakeGraph:
            async def ainvoke(self, payload, config=None):
                return {"messages": [AIMessage(content="答")], "routed_skill": "receiving"}

        service = LangChainAgentService(_FakeGraph())
        resp = asyncio.run(service.run(AgentRequest(
            messages=[{"role": "user", "content": "hi"}], thread_id="t1",
        )))
        self.assertEqual(resp.reply, "答")
        self.assertEqual(resp.routed_skill, "receiving")


class StreamRoutingIntegrationTest(unittest.TestCase):
    """真图流式:routing 帧先于 token,done 收尾。"""

    def test_stream_emits_routing_then_done(self) -> None:
        class _StubRecognizer:
            async def recognize(self, messages, skills):
                return IntentClassification(target_skill="receiving", confidence=0.9)

        graph = build_conversation_agent(
            llm=GenericFakeChatModel(messages=iter([AIMessage(content="好的")])),
            identity=AgentIdentity(persona="AI 账票助手", tones="专业简洁"),
            skills=[SkillConfig(name="receiving", description="收票", task_instructions="处理收票任务")],
            general_skill=SkillConfig(name="general", description="通用", task_instructions="通用应答"),
            recognizer=_StubRecognizer(),
            policy=RoutingPolicy(RoutingConfig()),
            checkpointer=MemorySaver(),
        )
        service = LangChainAgentService(graph)

        async def collect() -> list:
            events = []
            async for ev in service.stream(AgentRequest(
                messages=[{"role": "user", "content": "录发票"}], thread_id="t-sse",
            )):
                events.append(ev)
            return events

        events = asyncio.run(collect())
        types = [e.event_type for e in events]
        self.assertIn("routing", types)
        self.assertIn("done", types)
        self.assertLess(types.index("routing"), types.index("done"))
        routing = events[types.index("routing")]
        self.assertEqual(routing.skill_name, "receiving")


if __name__ == "__main__":
    unittest.main()
