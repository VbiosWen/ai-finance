"""FastAPI 服务启动入口。

职责：
- 通过 create_app 工厂创建 FastAPI app（含 lifespan + 路由）
- 启动 uvicorn

create_app 统一管理: lifespan → Container 装配 → 路由注册 → 优雅关闭。
"""
from __future__ import annotations

from bootstrap.app import create_app

app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
