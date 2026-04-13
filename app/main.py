from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from contextlib import asynccontextmanager
import os

from app.config import settings
from app.database import engine, Base, get_db
from app.schemas import TaskCreate, TaskResponse, AnalysisResultResponse
from app.models import Task, AnalysisResult
from app.tasks import crypto_sentiment_analysis

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时：创建数据库表
    async with engine.begin() as conn:
        # 在生产环境中建议使用 Alembic 迁移而不是直接 create_all
        # 但为了快速运行和演示，这里先启用表自动创建
        await conn.run_sync(Base.metadata.create_all)
    yield
    # 关闭时：清理资源
    await engine.dispose()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan
)

# 挂载静态文件目录
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
if not os.path.exists(STATIC_DIR):
    os.makedirs(STATIC_DIR)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def index():
    """返回主页前端界面"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>AetherCrawler UI is not built yet.</h1>"

@app.get("/health", tags=["Health"])
async def health_check():
    """基础健康检查"""
    return {
        "status": "ok",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

@app.post("/analyze-crypto", response_model=TaskResponse, status_code=status.HTTP_202_ACCEPTED, tags=["Analysis"])
async def analyze_crypto(task_in: TaskCreate, db: AsyncSession = Depends(get_db)):
    """
    提交一个加密货币情绪分析任务。
    这是一个异步请求，将触发后台 Celery 任务，并返回用于查询状态的 task_id。
    """
    coin = task_in.coin.lower().strip()
    
    # 将任务推送到 Celery
    celery_task = crypto_sentiment_analysis.delay(coin, task_in.days)
    
    # 记录到 PostgreSQL 数据库中
    new_task = Task(
        celery_task_id=celery_task.id,
        coin=coin,
        status="PENDING"
    )
    db.add(new_task)
    await db.commit()
    await db.refresh(new_task)
    
    # 构造返回字典，避免 Pydantic 在模型转换时触发 relationship 懒加载导致的 MissingGreenlet 错误
    return {
        "id": new_task.id,
        "celery_task_id": new_task.celery_task_id,
        "coin": new_task.coin,
        "status": new_task.status,
        "created_at": new_task.created_at,
        "updated_at": new_task.updated_at,
        "result": None
    }

@app.get("/tasks/{task_id}", response_model=TaskResponse, tags=["Analysis"])
async def get_task_status(task_id: int, db: AsyncSession = Depends(get_db)):
    """
    通过数据库内部 ID 查询任务的执行状态，如果成功则包含最终的分析结果。
    """
    stmt = select(Task).where(Task.id == task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # 由于我们在 models.py 中使用了 relationship，并且由于是懒加载
    # 对于异步，我们需要显示关联查询结果，或利用 await task.awaitable_attrs.result (SQLAlchemy 2.0 特性)
    # 简单起见，我们直接查询 Result 表
    if task.status == "SUCCESS":
        result_stmt = select(AnalysisResult).where(AnalysisResult.task_id == task.id)
        res = await db.execute(result_stmt)
        analysis = res.scalar_one_or_none()
    else:
        analysis = None
        
    return {
        "id": task.id,
        "celery_task_id": task.celery_task_id,
        "coin": task.coin,
        "status": task.status,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "result": analysis
    }

@app.get("/tasks/celery/{celery_task_id}", response_model=TaskResponse, tags=["Analysis"])
async def get_task_by_celery_id(celery_task_id: str, db: AsyncSession = Depends(get_db)):
    """
    通过 Celery Task ID 查询任务状态
    """
    stmt = select(Task).where(Task.celery_task_id == celery_task_id)
    result = await db.execute(stmt)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.status == "SUCCESS":
        result_stmt = select(AnalysisResult).where(AnalysisResult.task_id == task.id)
        res = await db.execute(result_stmt)
        analysis = res.scalar_one_or_none()
    else:
        analysis = None
        
    return {
        "id": task.id,
        "celery_task_id": task.celery_task_id,
        "coin": task.coin,
        "status": task.status,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "result": analysis
    }

@app.get("/analysis/{coin}", response_model=List[AnalysisResultResponse], tags=["Analysis"])
async def get_coin_analysis(coin: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    获取某个币种最近的分析报告历史列表
    """
    coin = coin.lower().strip()
    stmt = (
        select(AnalysisResult)
        .where(AnalysisResult.coin == coin)
        .order_by(AnalysisResult.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    reports = result.scalars().all()
    
    return reports

@app.get("/history/recent", response_model=List[AnalysisResultResponse], tags=["Analysis"])
async def get_recent_history(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    获取全局最新分析报告历史列表
    """
    stmt = (
        select(AnalysisResult)
        .order_by(AnalysisResult.created_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    reports = result.scalars().all()
    
    return reports

@app.delete("/history/{report_id}", tags=["Analysis"])
async def delete_history_report(report_id: int, db: AsyncSession = Depends(get_db)):
    """
    删除指定的历史分析报告
    """
    stmt = select(AnalysisResult).where(AnalysisResult.id == report_id)
    result = await db.execute(stmt)
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    
    await db.delete(report)
    await db.commit()
    return {"message": "Deleted successfully"}
