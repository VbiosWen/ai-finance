# ============================================================================
# AI Finance 账票服务 Docker 镜像
# ============================================================================
# 构建:
#   docker build -t ai-finance:latest .
#
# 运行:
#   docker run -d -p 8000:8000 \
#     -e NACOS_ADDRESS=nacos:8848 \
#     -e NACOS_NAMESPACE=ai-finance \
#     ai-finance:latest
# ============================================================================

# ── Stage 1: 构建依赖 ──────────────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:0.8.0-python3.11-bookworm AS builder

WORKDIR /app

# 先复制依赖描述文件，利用 Docker 缓存层
COPY pyproject.toml uv.lock ./

# 安装生产依赖到虚拟环境
RUN uv sync --frozen --no-dev --no-install-project

# ── Stage 2: 运行镜像 ──────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

WORKDIR /app

# 安装运行时系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# 从 builder 复制虚拟环境
COPY --from=builder /app/.venv /app/.venv

# 复制应用源码
COPY src/ /app/src/
COPY main.py /app/main.py

# 将虚拟环境加入 PATH，使 uv run 和包入口直接可用
ENV PATH="/app/.venv/bin:$PATH"

# 服务端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# 启动服务
CMD ["python", "main.py"]
