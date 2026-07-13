"""免配置启动器:免安装即可从项目根运行 `python main.py`。

正式部署用打包后的入口:`ai-finance`(见 pyproject.toml [project.scripts])。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from bootstrap.main import main

if __name__ == "__main__":
    main()
