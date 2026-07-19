"""配置仓储泛型端口。

定义了从外部配置源（Nacos、本地文件等）读取和监听配置变更的通用抽象。
具体业务配置（AgentIdentity、SkillConfig 等）应继承此端口并绑定具体类型。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Generic, TypeVar

T = TypeVar("T")
"""配置值类型（输出）"""
P = TypeVar("P")
"""查询键类型（输入）"""


class ConfigRepository(ABC, Generic[T, P]):
    """配置仓储抽象基类。

    定义 key-value 风格的配置访问模式，每个具体仓储负责一种配置类型。

    Type Parameters:
        T: 配置的值类型（如 ``AgentIdentity``、``list[SkillConfig]``）。
        P: 查询键类型（通常为 ``str``）。
    """

    @abstractmethod
    def get(self, key: P) -> T:
        """按键查询配置。

        Args:
            key: 配置键。

        Returns:
            对应类型的配置对象。

        Raises:
            KeyError: 配置不存在时抛出。
            RuntimeError: 尚未完成首次加载时抛出。
        """
        ...

    @abstractmethod
    def watch(self, callback: Callable[[T], None]) -> None:
        """注册配置变更回调。

        当远程配置发生热更新时，所有已注册的回调会按序触发。

        Args:
            callback: 接收新配置值的回调函数。
        """
        ...
