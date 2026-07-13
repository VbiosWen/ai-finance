"""服务启动入口。

运行方式:
    PYTHONPATH=src python -m bootstrap.main
或(项目根,免配置):
    python main.py
"""
from __future__ import annotations

import logging

from bootstrap.container import build_container

logger = logging.getLogger("ai-finance")


def main() -> None:
    """装配组合根并启动服务。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    container = build_container()
    logger.info("账票服务启动完成,组合根已装配:%s", type(container).__name__)
    # 选定 Web 框架后在此创建并运行 app,例如:
    #   from interfaces.http import create_app
    #   uvicorn.run(create_app(container), host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
