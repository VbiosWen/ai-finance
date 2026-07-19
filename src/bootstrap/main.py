"""服务启动入口:以 uvicorn factory 模式运行应用工厂。

应用装配见 bootstrap/app.py(create_app + lifespan),
依赖装配见 bootstrap/container.py(build_container)。
开发热重载:uv run uvicorn bootstrap.app:create_app --factory --reload
"""
from __future__ import annotations

import os


def main() -> None:
    import uvicorn

    uvicorn.run(
        "bootstrap.app:create_app",
        factory=True,
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
    )


if __name__ == "__main__":
    main()
