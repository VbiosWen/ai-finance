"""发送消息用例——对话闭环编排。业务规则在 domain,多轮记忆在 LangGraph checkpointer。"""
from __future__ import annotations

from application.conversation.commands import ChatResult, SendMessageCommand
from application.dto.agent_dto import AgentRequest
from application.ports.agent_service import AgentService
from application.ports.event_publisher import DomainEventPublisher
from domain.conversation.aggregate import Conversation
from domain.conversation.repository import ConversationRepository
from domain.conversation.value_objects import ConversationId


class SendMessageUseCase:
    def __init__(
        self,
        repo: ConversationRepository,
        agent: AgentService,
        publisher: DomainEventPublisher,
    ) -> None:
        self._repo = repo
        self._agent = agent
        self._publisher = publisher

    async def execute(self, cmd: SendMessageCommand) -> ChatResult:
        convo = None
        if cmd.conversation_id:
            convo = await self._repo.get_head(ConversationId(value=cmd.conversation_id))
        if convo is None:
            convo = Conversation.start(cmd.agent_id)

        convo.post_user_message(cmd.content)                       # 领域把门:CLOSED 拒绝
        request = AgentRequest(
            messages=[{"role": "user", "content": cmd.content}],   # 只喂最新一条
            thread_id=convo.id.value,                              # 驱动 checkpointer 记忆
        )
        response = await self._agent.run(request)                  # 图内:回放→路由→压缩→执行
        convo.record_assistant_message(response.reply)

        await self._repo.save(convo)
        for ev in convo.pull_events():
            await self._publisher.publish(ev)
        return ChatResult(conversation_id=convo.id.value, reply=response.reply)
