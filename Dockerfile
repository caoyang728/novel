# syntax=docker/dockerfile:1.6
# Novel Agent 生产镜像（Debian slim → apt/pip 都切国内源，避免 Docker build 在国内网络长时间卡住）
FROM python:3.14-slim

WORKDIR /app

# 系统依赖：PostgreSQL client + libpq（BuildKit 缓存 apt 包，避免每次 rebuild 从外网拉 .deb）
# 1) debian.sources（bookworm/trixie 新格式）/ sources.list（老格式）双保险切 aliyun 镜像
# 2) 强制 IPv4，避免 V6 黑洞路由导致 “Packages 下载卡住无进度”
# 3) apt 层单独加 Acquire Retries/Timeout，解决 99% 的国内网络长停问题
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    set -eux; \
    SRC_FILE=/etc/apt/sources.list.d/debian.sources; \
    if [ -f "$SRC_FILE" ]; then \
        sed -i -E 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' "$SRC_FILE"; \
    elif [ -f /etc/apt/sources.list ]; then \
        sed -i -E 's|deb.debian.org|mirrors.aliyun.com|g; s|security.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list; \
    fi; \
    { \
        echo 'Acquire::ForceIPv4 "true";'; \
        echo 'Acquire::Retries "5";'; \
        echo 'Acquire::http::Timeout "30";'; \
        echo 'Acquire::https::Timeout "30";'; \
        echo 'Acquire::http::Pipeline-Depth "0";'; \
    } > /etc/apt/apt.conf.d/99-cn-network-tuning; \
    apt-get update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ca-certificates \
        gcc \
        postgresql-client \
        tzdata; \
    rm -rf /var/lib/apt/lists/*

# Python 依赖层（单独 COPY requirements + BuildKit pip 缓存，代码变动不触发重下）
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip,sharing=locked \
    set -eux; \
    PIP_MIRROR="https://mirrors.aliyun.com/pypi/simple/"; \
    pip config --global set global.index-url "$PIP_MIRROR"; \
    pip config --global set global.trusted-host "mirrors.aliyun.com"; \
    pip config --global set install.timeout "120"; \
    pip install --upgrade pip setuptools wheel; \
    pip install --no-cache-dir -r requirements.txt

# 项目代码 + 入口脚本
COPY . .
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["/entrypoint.sh"]
