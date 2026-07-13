"""启动层 / 组合根 (Bootstrap / Composition Root)。

唯一允许依赖所有层的地方:装配依赖、把 infrastructure 的实现
接到 domain 定义的接口上、挂载 interfaces 路由、创建并启动服务。
"""
