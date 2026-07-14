"""AgentService 测试——验证 LangChainAgentService 的消息转换与适配逻辑。"""
from __future__ import annotations

import unittest

from langchain_core.messages import AIMessage, HumanMessage

from application.dto.agent_dto import AgentRequest
from interfaces.ai.react_agent import (
    _build_config,
    _count_tool_calls,
    _extract_last_ai_content,
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


if __name__ == "__main__":
    unittest.main()
