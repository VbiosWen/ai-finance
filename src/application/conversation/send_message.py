"""发送消息用例 —— 对话闭环编排。业务规则在 domain，此处只编排。"""
from __future__ import annotations

from application.conversation.commands import ChatResult, SendMessageCommand
from application.dto.agent_dto import AgentRequest
from application.ports.agent_service import AgentService
from application.ports.event_publisher import DomainEventPublisher
from domain.conversation.aggregate import Conversation
from domain.conversation.context_window import ContextWindowPolicy
from domain.conversation.repository import ConversationRepository
from domain.conversation.value_objects import ConversationId


class SendMessageUseCase:
    def __init__(
        self,
        repo: ConversationRepository,
        agent: AgentService,
        publisher: DomainEventPublisher,
        window: ContextWindowPolicy,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._publisher = publisher
        self._window = window

    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        convo = None
        if cmd.conversation_id:
            convo = await self._repo.get(
                ConversationId(value=cmd.conversation_id), window=self._window.size
            )
        if convo is None:
            convo = Conversation.start(cmd.agent_id)

        convo.post_user_message(cmd.content)                       # 领域
        history = self._window.select(convo.messages)              # 领域策略
        request = AgentRequest(
            messages=[{"role": m.role.value, "content": m.content} for m in history],
            thread_id=convo.id.value,   # 仅用于链路追踪，不再驱动记忆
        )
        response = await self._agent.run(request)                  # LangGraph 无状态
        convo.record_assistant_message(response.reply)            # 领域

        await self._repo.save(convo)
        for ev in convo.pull_events():
            await self._publisher.publish(ev)
        return ChatResult(conversation_id=convo.id.value, reply=response.reply)
