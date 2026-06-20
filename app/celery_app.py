import os
from celery import Celery
from celery.schedules import crontab
from app.config import settings

# 确保在运行 Celery worker 时能够找到正确的配置
# os.environ.setdefault('CELERY_CONFIG_MODULE', 'app.config')

celery_app = Celery(
    "aethercrawler",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.tasks"] # 自动发现 tasks.py 中的任务
)

# Celery 基础配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",  # 使用中国时区，方便配置定时任务
    enable_utc=True,
    
    # 任务执行时间限制
    task_time_limit=300,        # 软限制: 5分钟 (Playwright 爬取和 OpenAI 可能会慢)
    task_soft_time_limit=240,   # 硬限制之前 1 分钟抛出异常
    
    # 限制并发行为 (可根据机器配置调整 worker 并发数)
    worker_prefetch_multiplier=1,
    
    # 防止因数据库或网络连接导致的死锁
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ==========================================
# Celery Beat 定时任务配置
# ==========================================
# 说明：
# 1. 定时任务需要在启动 Beat 服务后才会执行：
#    本地开发：celery -A app.celery_app beat -l info
#    Docker 环境：需要在 docker-compose.yml 中添加 beat 服务
# 2. 时区：使用 Asia/Shanghai，配置时间为本地时间
#    早上 8 点 = hour=8, minute=0
#    晚上 20 点 = hour=20, minute=0
# ==========================================
celery_app.conf.beat_schedule = {
    # 每天早上 8 点分析 BTC
    'daily-btc-morning': {
        'task': 'app.tasks.crypto_sentiment_analysis',
        'schedule': crontab(hour=8, minute=0),
        'args': ('bitcoin',),
    },
    # 每天早上 8 点分析 ETH
    'daily-eth-morning': {
        'task': 'app.tasks.crypto_sentiment_analysis',
        'schedule': crontab(hour=8, minute=0),
        'args': ('ethereum',),
    },
    # 每天晚上 20 点分析 BTC
    'daily-btc-evening': {
        'task': 'app.tasks.crypto_sentiment_analysis',
        'schedule': crontab(hour=20, minute=0),
        'args': ('bitcoin',),
    },
    # 每天晚上 20 点分析 ETH
    'daily-eth-evening': {
        'task': 'app.tasks.crypto_sentiment_analysis',
        'schedule': crontab(hour=20, minute=0),
        'args': ('ethereum',),
    },
}
