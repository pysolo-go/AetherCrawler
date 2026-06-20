# AetherCrawler 产品优化建议书

> 本文档用于：向其他 AI 大模型展示项目现状与优化方向，以便进行进一步的自动化开发与迭代。

---

## 一、项目现状概述

**AetherCrawler** 是一个基于 AI 的加密货币情绪分析平台，已具备以下能力：

* **分布式架构**：FastAPI + Celery + Redis + PostgreSQL + Docker Compose
* **多维数据采集**：CoinGecko 价格数据、Playwright 新闻爬虫（CoinDesk）、恐惧贪婪指数（Alternative.me）
* **AI 推理引擎**：接入阿里云通义千问（qwen-plus），针对短线交易（15m/1H）进行提示词精调，强制输出中文结构化研报
* **可视化前端**：暗黑科技风 SPA（Vue.js 3 + TailwindCSS），集成 TradingView 实时 K 线组件，包含假终端日志动画和历史报告管理功能
* **已开源发布**：代码已推送至 GitHub `pysolo-go/AetherCrawler`，支持 Docker 一键部署

---

## 二、现有问题与不足

### 2.1 数据源单一且不稳定

| 当前状态 | 问题 | 优化方向 |
|---------|------|---------|
| CoinGecko 价格 | 数据有延迟，1H 粒度够用 | 可考虑接入 Binance/OKX 实时 K 线 |
| Playwright 新闻爬虫 | CoinDesk 经常超时（30s），成功率低，维护成本高 | 改用 NewsAPI / CryptoPanic 等结构化接口 |
| Alternative.me F&G | 官方接口，稳定性好 | 保留，继续沿用 |
| Binance 合约数据 | 返回 451 被墙 | 改用 OKX 合约 API（OKX 对大陆更友好） |
| 链上数据缺失 | 无 Glassnode / CryptoQuant | 接入链上数据可大幅提升分析深度 |
| 社交舆情缺失 | 无 Twitter/X、Reddit、Telegram 情绪数据 | 可接 CryptoBuzz 等聚合接口 |

### 2.2 缺乏主动预警机制

**现状：** 用户必须主动打开网页点击分析，属于"被动查询"工具。

**对比专业产品：** 同花顺、TradingView、币世界等均有价格异动预警、多空比突变通知。

**建议：** 接入 Webhook（飞书机器人 / 钉钉机器人 / Discord Webhook），当 AI 分析结果出现极端信号（如情绪分数 < 0.3 或 > 0.8）时，自动推送通知到手机。

### 2.3 无法定时自动分析

**现状：** 每次需要手动触发分析，等待 1-2 分钟才能看到结果。

**建议：** 配置 Celery Beat 定时任务，每天固定时间（如早 8:00、晚 22:00）自动执行 BTC + ETH 的分析并推送结果。

### 2.4 单币种分析，缺乏宏观视角

**现状：** 一次只能分析一个币，没有"主流币情绪总览"仪表盘。

**建议：** 增加"多币种概览"页面，同时展示 BTC / ETH / SOL 的情绪分数、24H 涨跌幅、F&G 指数，做横向对比。

### 2.5 无历史预测追踪与胜率回测

**现状：** AI 给出做多/做空结论后没有追踪记录，无法验证准确性。

**建议：** 增加"历史预测表"，记录每次 AI 的 bias 结论，并在 N 小时/天后自动对比实际走势，计算胜率。

### 2.6 无用户系统（可选）

**现状：** 所有用户共享同一个数据库，无登录与个性化功能。

**建议：** 如果仅个人使用可跳过；如需产品化，需增加用户认证与偏好设置。

---

## 三、优化方向优先级

```
优先级排序：

⭐⭐⭐ [P0] 接入 NewsAPI 替代不稳定爬虫
     → 解决新闻获取超时痛点，提升分析稳定性
     → 预估工作量：0.5 天

⭐⭐⭐ [P0] 配置每日定时自动分析 + 飞书 Webhook 通知
     → 让工具真正实现"自动化"，无需手动触发
     → 预估工作量：1 天

⭐⭐  [P1] 增加"主流币情绪总览"多币种仪表盘
     → 提升信息密度，一眼掌握全局情绪
     → 预估工作量：1 天

⭐⭐  [P1] 改用 OKX 合约 API 替代 Binance（被墙）
     → 修复多空比数据获取问题
     → 预估工作量：2 小时

⭐   [P2] 接入链上数据（Glassnode / CryptoQuant）
     → 大幅提升 AI 分析深度
     → 预估工作量：2-3 天

⭐   [P2] 历史预测追踪与胜率回测功能
     → 帮助用户复盘 AI 准确度
     → 预估工作量：3 天

⭐   [P3] 用户系统与个性化设置
     → 仅面向产品化需求，个人使用可跳过
     → 预估工作量：3-5 天
```

---

## 四、技术债务

* Playwright 依赖较重（启动浏览器开销 ~3-5s），可考虑用 httpx + BeautifulSoup 替代轻量爬虫
* 当前 Celery 配置为单 Worker，生产环境建议增加 Worker 数量以提高并发
* 数据库目前存储在 Docker Volume，建议迁移至独立 PostgreSQL 服务以提升数据持久性

---

## 五、参考竞品

| 产品 | 亮点 | AetherCrawler 可借鉴之处 |
|------|------|------------------------|
| TradingView | 强大图表生态、量化指标 | 接入更多技术指标（RSI、MACD、布林带） |
| 币世界 / 币Coin | 实时快讯推送、社群情绪聚合 | 接入 Telegram / Twitter 舆情 |
| Glassnode | 专业链上指标 | 接入 Glassnode API |
| 同花顺问财 | 智能投研助手 | 增强 AI 研报格式，支持 PDF 导出 |

---

## 六、下一步开发指令（可复制给 AI Agent）

```
请基于 AetherCrawler 项目（https://github.com/pysolo-go/AetherCrawler），
优先完成以下两个任务：

任务 1：接入 NewsAPI 替代 Playwright 爬虫
- 注册 NewsAPI (https://newsapi.org)，获取免费 API Key
- 修改 app/tasks.py 中的 crawl_crypto_news 函数
- 优先抓取 crypto 相关的英文新闻，翻译后作为 AI 分析上下文
- 保留 Playwright 作为备用降级方案（NewsAPI 免费版有请求频率限制）

任务 2：配置定时任务 + 飞书 Webhook 通知
- 修改 app/celery_app.py，增加 Celery Beat 配置
- 设置每天 08:00 和 20:00 自动执行 BTC + ETH 的情绪分析
- 接入飞书自定义机器人 Webhook
- 当情绪分数 < 0.35（极度恐慌）或 > 0.75（极度贪婪）时，自动发送分析摘要到飞书群

请确保所有代码改动符合原项目的代码风格，中文输出，完成后更新 README.md。
```

---

*文档生成时间：2026-06-20*
*项目地址：https://github.com/pysolo-go/AetherCrawler*
