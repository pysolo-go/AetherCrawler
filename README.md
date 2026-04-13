# AetherCrawler 🚀

> 这是一个由 AI 驱动的工业级加密货币情绪分析平台。系统通过分布式爬虫实时抓取市场新闻与社交情绪，结合全网价格异动，利用阿里云通义千问 (Qwen) 等大模型进行深度推理，最后在现代化、暗黑玻璃拟物风的 Web 端呈现直观的交易研报与实时 K 线。

---

## 🌟 核心特性

*   **分布式架构**：基于 `FastAPI` (Web API) + `Celery` (后台异步任务队列) + `Redis` (消息代理) + `PostgreSQL` (持久化存储) 的生产级架构。
*   **多维数据采集**：
    *   利用异步爬虫自动抓取 `CoinDesk` 等权威媒体的最新资讯。
    *   通过 `CoinGecko` API 拉取加密货币的实时价格、24H 高低点、市值及历史交易量。
    *   通过 `Alternative.me` 实时抓取“恐慌与贪婪指数 (Fear & Greed Index)”。
*   **AI 深度推理 (Qwen)**：
    *   针对短线交易者（15m / 1H 级别）进行提示词精调。
    *   对短线急跌（如 1.5% 跌幅）具有高敏感度，自动分析是否为“恐慌抛售”、“洗盘”或“出货”。
    *   强制输出结构化的纯中文研报（包含看多/看空结论、情绪分数、逻辑分析及关键催化剂）。
*   **高颜值可视化前端 (SPA)**：
    *   单页应用设计，纯前端无需 Node.js 构建，采用 `Vue.js 3` + `TailwindCSS`。
    *   暗黑极客风，带有毛玻璃 (Glassmorphism) 效果。
    *   内置“实时执行日志”终端动画，大幅缓解 AI 推理期间的用户等待焦虑。
    *   无缝集成 `TradingView` 官方高级实时 K 线组件，支持画线与交互。
*   **容器化一键部署**：全套组件打包于 `Docker` 和 `Docker Compose`，无论是 Mac 本地还是 Linux 云服务器，一行命令即可启动运行。

---

## 🛠️ 技术栈

*   **后端 Backend**: Python 3.11, FastAPI, SQLAlchemy, Pydantic, httpx
*   **异步任务 Async Tasks**: Celery, Redis
*   **数据库 Database**: PostgreSQL, asyncpg
*   **AI 推理引擎 LLM**: LangChain, OpenAI API 协议兼容 (当前配置为阿里云通义千问 `qwen-plus`)
*   **前端 Frontend**: HTML5, Vue.js 3 (CDN), TailwindCSS (CDN), Phosphor Icons, TradingView Advanced Chart Widget
*   **部署 Deployment**: Docker, Docker Compose

---

## 🚀 快速启动 (Quick Start)

### 1. 环境准备

请确保你的机器上已安装：
*   [Docker](https://www.docker.com/products/docker-desktop)
*   [Docker Compose](https://docs.docker.com/compose/install/)

### 2. 配置环境变量

克隆仓库后，复制示例环境文件并填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的大模型 API 密钥：

```ini
# 示例：使用阿里云通义千问
OPENAI_API_KEY="sk-你的通义千问API密钥"
OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
OPENAI_MODEL_NAME="qwen-plus"

# 如果你在国内运行且需要爬取外网新闻，请配置代理（需确保 Docker 容器能访问到该端口）
# HTTP_PROXY=http://host.docker.internal:7897
```

### 3. 一键启动

在项目根目录下运行：

```bash
docker-compose up -d --build
```

*初次启动时，Docker 会自动拉取所需的 Python, Redis, Postgres 镜像，并安装所有依赖。*

### 4. 访问应用

启动成功后，打开浏览器访问：

👉 **[http://localhost:8000](http://localhost:8000)**

---

## � 项目目录结构

```text
AetherCrawler/
├── app/
│   ├── __init__.py
│   ├── celery_app.py    # Celery 实例与配置
│   ├── config.py        # Pydantic 环境变量管理
│   ├── database.py      # SQLAlchemy 异步数据库连接
│   ├── main.py          # FastAPI 路由与应用入口
│   ├── models.py        # 数据库 ORM 模型 (Task, AnalysisResult)
│   ├── schemas.py       # Pydantic 请求/响应数据校验模型
│   ├── tasks.py         # Celery 异步任务 (爬虫逻辑、大模型调用)
│   ├── utils.py         # 工具函数 (LangChain 提示词组装、API 抓取实现)
│   └── static/          # 静态文件目录
│       └── index.html   # Vue.js + Tailwind 核心前端页面
├── docker-compose.yml   # 多容器编排配置
├── Dockerfile           # Web 和 Worker 容器的构建文件
├── requirements.txt     # Python 依赖清单
├── .env.example         # 环境变量示例
└── README.md            # 项目说明文档
```

---

## � 开发与调试

**查看实时日志：**
```bash
# 查看所有容器日志
docker-compose logs -f

# 仅查看爬虫与 AI 分析任务日志
docker-compose logs -f worker
```

**清理数据库与重置：**
```bash
# 停止并删除容器、网络和数据卷 (会清空 PostgreSQL 数据)
docker-compose down -v
```

---

## 📄 License

This project is licensed under the MIT License.