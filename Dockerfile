FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 优化构建速度：替换 apt-get 和 pip 的镜像源为阿里云（解决国内下载慢的问题）
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list.d/debian.sources && \
    pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/

# 设置环境变量，防止 python 缓存和 stdout 缓冲
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 安装系统依赖 (为 Playwright 所需的部分系统包做准备)
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 拷贝 requirements 并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 单独安装 Playwright 浏览器及其系统依赖项
RUN playwright install chromium
RUN playwright install-deps chromium

# 拷贝整个项目代码
COPY . .

# 暴露 FastAPI 端口
EXPOSE 8000

# 默认运行 FastAPI 生产级服务器（在 docker-compose 中会被覆盖以支持不同角色的容器）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
