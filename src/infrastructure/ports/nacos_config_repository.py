"""Nacos 配置仓储端口。

定义了从 Nacos 配置中心拉取配置、监听变更的抽象接口。
具体实现由各环境（本地文件、Nacos SDK）提供，通过依赖注入在 bootstrap 层装配。
"""

from abc import ABC, abstractmethod


class NacosConfigRepository(ABC):
    """Nacos 配置仓储抽象基类。

    负责从 Nacos 配置中心加载业务配置（如 LLM 参数、数据库连接信息等），
    并监听远程配置变更以实现热更新。

    使用方式：
        1. 实现 ``load()`` 方法，完成首次配置拉取与解析。
        2. 在 load() 中注册 ``_on_config_changed`` 为 Nacos 回调，
           当远程配置发生变更时自动触发。
    """

    @abstractmethod
    async def load(self) -> None:
        """从 Nacos 拉取配置并写入本地缓存/配置对象。

        具体实现应：
        - 连接 Nacos 服务端，获取指定 data_id 与 group 的配置内容。
        - 将原始配置解析为领域层可用的结构化配置对象。
        - 注册 ``_on_config_changed`` 作为配置变更监听回调。

        Raises:
            ConnectionError: 无法连接 Nacos 服务端时抛出。
        """
        ...

    async def _on_config_changed(self, raw: str) -> None:
        """Nacos 配置变更回调。

        当 Nacos 服务端推送配置变更时，SDK 会调用此方法。
        子类可覆写以在配置热更新后执行额外逻辑（如刷新连接池、重建 LLM 客户端等）。

        Args:
            raw: Nacos 推送的原始配置内容（通常为 JSON / YAML 字符串）。
        """
        ...