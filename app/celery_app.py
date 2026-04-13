import os
from celery import Celery
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
    timezone="UTC",
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

# 可选: 定时任务配置入口 (Celery Beat)
# celery_app.conf.beat_schedule = {
#     'daily-bitcoin-analysis': {
#         'task': 'app.tasks.crypto_sentiment_analysis',
#         'schedule': crontab(hour=0, minute=0),
#         'args': ('bitcoin',),
#     },
# }
