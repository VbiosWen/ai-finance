"""兜底通用技能 —— 接住一切无法归类的请求，保证体验连贯。"""
from __future__ import annotations

from domain.value_objects.skill_config import SkillConfig

GENERAL_SKILL = SkillConfig(
    name="general",
    description="通用助手，处理未匹配到专业技能的账票相关请求以及日常对话。",
    task_instructions=(
        "作为账票领域的通用助手，礼貌地理解用户意图并尽力回答；"
        "遇到明显属于收票或稽核的专业请求时，正常作答即可。"
    ),
    version="1.0.0",
)
