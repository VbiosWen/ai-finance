"""InMemoryEventPublisher 测试——按类型分发，未订阅类型 no-op。"""
from __future__ import annotations

import asyncio
import unittest

from domain.conversation.events import AssistantResponded, ConversationStarted
from infrastructure.conversation.event_publisher import InMemoryEventPublisher


class InMemoryEventPublisherTest(unittest.TestCase):
    def test_dispatch_to_subscriber(self) -> None:
        async def run() -> None:
            pub = InMemoryEventPublisher()
            seen: list = []
            pub.subscribe(ConversationStarted, lambda ev: seen.append(ev))
            await pub.publish(ConversationStarted(conversation_id="c1", agent_id="a"))
            self.assertEqual(len(seen), 1)

        asyncio.run(run())

    def test_async_handler_awaited(self) -> None:
        async def run() -> None:
            pub = InMemoryEventPublisher()
            seen: list = []

            async def handler(ev) -> None:
                seen.append(ev)

            pub.subscribe(ConversationStarted, handler)
            await pub.publish(ConversationStarted(conversation_id="c1", agent_id="a"))
            self.assertEqual(len(seen), 1)

        asyncio.run(run())

    def test_unsubscribed_type_is_noop(self) -> None:
        async def run() -> None:
            pub = InMemoryEventPublisher()
            await pub.publish(AssistantResponded(conversation_id="c1", content="x"))  # 不抛错

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
