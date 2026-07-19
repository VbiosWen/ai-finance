"""AgentIdentity 配置仓储端口。

定义 Agent 身份定义配置的访问契约，由基础设施层 Nacos 适配器实现。
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Callable

from domain.ports.config_repository import ConfigRepository
from domain.value_objects.agent_identity import AgentIdentity


class AgentIdentityRepository(ConfigRepository[AgentIdentity, str]):
    """Agent 身份定义的配置仓储。

    每个 key 对应一个 ``AgentIdentity`` 实例。
    """

    @abstractmethod
    def get(self, key: str) -> AgentIdentity:
        """获取指定 key 的 Agent 身份定义。

        Args:
            key: 配置键（如 ``"agent-identity"``）。

        Returns:
            对应 key 的 AgentIdentity 值对象。

        Raises:
            KeyError: key 不存在。
            RuntimeError: 尚未完成首次加载。
        """
        ...

    @abstractmethod
    def watch(self, callback: Callable[[AgentIdentity], None]) -> None:
        """注册 AgentIdentity 变更回调。

        Args:
            callback: 接收新的 AgentIdentity 实例的回调函数。
        """
        ...
