"""组合根:集中装配各层依赖。

业务落地后,这里负责:
- 创建基础设施(数据库会话、事件总线、外部适配器)
- 用 infrastructure 的实现装配 domain 定义的仓储/端口接口
- 注册应用层的命令/事件处理器

当前是最小骨架,仅提供占位的装配入口。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Container:
    """持有已装配好的依赖,供 interfaces 与启动流程取用。"""

    # 随业务接入,例如:
    #   invoice_repository: "InvoiceRepository"
    #   message_bus: "MessageBus"


def build_container() -> Container:
    """构建并返回组合根容器。

    真正接入数据库、事件总线、仓储实现时在此处装配。
    """
    return Container()
