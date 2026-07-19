from domain.entities.agent_entity import AgentEntity
from domain.shared import AITool, ToolResult


class AgentRouterTool(AITool):

    name = ""
    description = ""

    def __init__(self, agent_entities : list[AgentEntity]) -> None:
        self._agent_entities : list[AgentEntity] = agent_entities
        self._agent_dict : dict[str, AgentEntity]


    async def execute(self, **kwargs: str) -> ToolResult:
        name = (kwargs.get("agent_name") or "").strip()

        if not name or name == "list" :
            if not self._agent_entities:
                return ToolResult(
                    success=True,
                    content="暂无可用agent。",
                    tool_name= self.name
                )
            