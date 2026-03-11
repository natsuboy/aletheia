FROM python:3.12-slim

# 替换 apt 源为阿里云 Debian 镜像（Bookworm）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# 安装 uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# 使用清华 PyPI 镜像加速 Python 包下载
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY pyproject.toml uv.lock* ./

# 安装依赖（使用 BuildKit 缓存加速重复构建）
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# 安装 Go (scip-go 需要 Go 运行时) 和 Git
# 使用 golang.google.cn 国内镜像加速下载
RUN apt-get update && apt-get install -y wget ca-certificates git && \
    wget -O /tmp/go.tar.gz https://golang.google.cn/dl/go1.25.0.linux-amd64.tar.gz && \
    tar -C /usr/local -xzf /tmp/go.tar.gz && \
    rm /tmp/go.tar.gz && \
    apt-get clean && rm -rf /var/lib/apt/lists/*
ENV PATH="/usr/local/go/bin:${PATH}"

# 复制 scip-go 二进制文件 (x86-64)
COPY bin/scip-go /usr/local/bin/scip-go

# 复制源代码
COPY src/ ./src/

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uv", "run", "uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
