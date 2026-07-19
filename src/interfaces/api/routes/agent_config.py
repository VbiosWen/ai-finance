"""Agent 配置只读路由——身份定义与技能列表。"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from domain.ports.agent_identity_repository import AgentIdentityRepository
from domain.ports.skill_config_repository import SkillConfigRepository
from interfaces.api.dependencies import get_agent_identity_repo, get_skill_config_repo

router = APIRouter(prefix="/agent", tags=["agent"])


@router.get("/identity")
async def agent_identity(
    repo: AgentIdentityRepository = Depends(get_agent_identity_repo),
) -> dict:
    return repo.get("agent-identity").model_dump()


@router.get("/skills")
async def agent_skills(
    repo: SkillConfigRepository = Depends(get_skill_config_repo),
) -> list[dict]:
    return [s.model_dump() for s in repo.get("skill-configs")]
