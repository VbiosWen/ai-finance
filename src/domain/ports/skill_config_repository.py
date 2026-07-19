"""SkillConfig 配置仓储端口。

定义技能配置的访问契约，由基础设施层 Nacos 适配器实现。
每个 key 对应一组技能配置列表（支持多技能场景）。
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable

from domain.ports.config_repository import ConfigRepository
from domain.value_objects.skill_config import SkillConfig


class SkillConfigRepository(ConfigRepository[list[SkillConfig], str]):
    """技能配置仓储。

    每个 key 对应一个 ``SkillConfig`` 列表（一个 Agent 可关联多个技能）。
    """

    @abstractmethod
    def get(self, key: str) -> list[SkillConfig]:
        """获取指定 key 的技能配置列表。

        Args:
            key: 配置键（如 ``"skill-configs"``）。

        Returns:
            技能配置列表，无数据时返回空列表。

        Raises:
            RuntimeError: 尚未完成首次加载。
        """
        ...

    @abstractmethod
    def watch(self, callback: Callable[[list[SkillConfig]], None]) -> None:
        """注册技能配置变更回调。

        Args:
            callback: 接收新的 SkillConfig 列表的回调函数。
        """
        ...
