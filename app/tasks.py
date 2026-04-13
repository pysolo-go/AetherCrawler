import asyncio
import httpx
import random
import json
import logging
from datetime import datetime
from typing import List, Dict, Any
from playwright.async_api import async_playwright
from sqlalchemy.future import select

from app.celery_app import celery_app
from app.database import async_session_maker
from app.models import Task, AnalysisResult
from app.utils import perform_sentiment_analysis
from app.config import settings

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:124.0) Gecko/20100101 Firefox/124.0",
]

async def fetch_coingecko_current_data(coin: str) -> Dict[str, Any]:
    """调用 CoinGecko API 获取当前价格数据（支持 24h 变化、市值等）"""
    url = f"{settings.COINGECKO_API_BASE}/simple/price"
    params = {
        "ids": coin,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_market_cap": "true",
        "include_24hr_vol": "true"
    }
    
    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return data.get(coin, {})
    except Exception as e:
        logger.error(f"CoinGecko 当前数据获取失败 ({coin}): {e}")
        return {}

async def fetch_coingecko_historical_data(coin: str, days: int = 7) -> Dict[str, Any]:
    """获取历史价格图表数据"""
    url = f"{settings.COINGECKO_API_BASE}/coins/{coin}/market_chart"
    params = {
        "vs_currency": "usd",
        "days": days,
        "interval": "daily" if days > 30 else "hourly"
    }
    try:
        async with httpx.AsyncClient(timeout=settings.HTTP_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            return {
                "prices": data.get("prices", []),
                "market_caps": data.get("market_caps", []),
                "total_volumes": data.get("total_volumes", [])
            }
    except Exception as e:
        logger.error(f"CoinGecko 历史数据获取失败 ({coin}): {e}")
        return {"prices": [], "market_caps": [], "total_volumes": []}

async def crawl_crypto_news(coin: str) -> List[str]:
    """异步 Playwright 爬取加密新闻网站 (如 CoinDesk、Decrypt)"""
    news_texts = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=settings.PLAYWRIGHT_HEADLESS)
        context = await browser.new_context(user_agent=random.choice(USER_AGENTS))
        
        try:
            # 网站 1: CoinDesk (搜索页/首页)
            page = await context.new_page()
            try:
                search_url = f"https://www.coindesk.com/search?s={coin}"
                await page.goto(search_url, timeout=settings.HTTP_TIMEOUT * 1000)
                await page.wait_for_timeout(3000)
                
                articles = await page.query_selector_all("h6, h2, .article-title")
                for article in articles[:5]:
                    text = await article.inner_text()
                    if text.strip() and len(text.strip()) > 10:
                        news_texts.append(f"CoinDesk: {text.strip()}")
            except Exception as e:
                logger.warning(f"Error crawling CoinDesk: {e}")
            finally:
                await page.close()
                
            # 网站 2: Decrypt
            page2 = await context.new_page()
            try:
                search_url2 = f"https://decrypt.co/search?q={coin}"
                await page2.goto(search_url2, timeout=settings.HTTP_TIMEOUT * 1000)
                await page2.wait_for_timeout(3000)
                
                articles = await page2.query_selector_all("h3, h2")
                for article in articles[:5]:
                    text = await article.inner_text()
                    if text.strip() and len(text.strip()) > 10:
                        news_texts.append(f"Decrypt: {text.strip()}")
            except Exception as e:
                logger.warning(f"Error crawling Decrypt: {e}")
            finally:
                await page2.close()

        finally:
            await browser.close()
            
    return news_texts

async def _run_analysis_pipeline(celery_task_id: str, coin: str, days: int = 7):
    """实际执行异步流程：更新数据库状态、调用外部API、爬取、大模型分析"""
    async with async_session_maker() as db:
        # 1. 查找对应的 Task 并更新状态
        stmt = select(Task).where(Task.celery_task_id == celery_task_id)
        result = await db.execute(stmt)
        db_task = result.scalar_one_or_none()
        
        if db_task:
            db_task.status = "STARTED"
            await db.commit()

        try:
            logger.info(f"开始分析币种: {coin}, 历史天数: {days}")
            
            # 2. 获取 CoinGecko 当前价格与历史数据
            current_data = await fetch_coingecko_current_data(coin)
            historical_data = await fetch_coingecko_historical_data(coin, days=days)
            
            # 3. 爬取新闻 (高并发异步)
            news_texts = await crawl_crypto_news(coin)
            
            # 4. AI情绪分析 (传入历史数据作为上下文)
            # 我们需要把 current_data 也塞进去，因为 prompt 里现在需要用到它
            historical_data["current_data"] = current_data
            analysis = await perform_sentiment_analysis(news_texts, coin, historical_data)
            
            # 5. 保存结果到数据库
            if db_task:
                analysis_result = AnalysisResult(
                    task_id=db_task.id,
                    coin=coin,
                    price_data=current_data,
                    historical_prices=historical_data.get("prices", []),
                    sentiment_score=analysis.get("sentiment_score", 0.5),
                    sentiment=analysis.get("sentiment", "Neutral"),
                    key_factors=analysis.get("key_factors", []),
                    summary=analysis.get("summary", ""),
                    risk_level=analysis.get("risk_level", "Medium"),
                    potential_catalysts=analysis.get("potential_catalysts", []),
                    raw_news=json.dumps(news_texts),
                    analysis_period_days=days
                )
                db.add(analysis_result)
                db_task.status = "SUCCESS"
                await db.commit()
                
            logger.info(f"币种 {coin} 分析完成，情绪分数: {analysis.get('sentiment_score')}")
            return {
                "coin": coin,
                "current_price": current_data,
                "historical_summary": f"过去 {days} 天数据已获取",
                "sentiment_score": analysis.get("sentiment_score"),
                "sentiment": analysis.get("sentiment"),
                "key_factors": analysis.get("key_factors"),
                "summary": analysis.get("summary"),
                "risk_level": analysis.get("risk_level"),
                "potential_catalysts": analysis.get("potential_catalysts")
            }
            
        except Exception as e:
            # 如果中间有异常，标记状态为失败
            if db_task:
                db_task.status = "FAILURE"
                await db.commit()
            raise e

@celery_app.task(name="tasks.crypto_sentiment_analysis", bind=True, max_retries=3, default_retry_delay=60)
def crypto_sentiment_analysis(self, coin: str = "bitcoin", days: int = 7):
    """
    加密货币情绪分析主任务
    """
    # 为了避免在 Fork 进程中重复使用同一个 asyncio 事件循环和数据库连接池，
    # 我们每次任务都创建一个全新的独立事件循环。
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        return loop.run_until_complete(_run_analysis_pipeline(self.request.id, coin, days))
    except Exception as exc:
        logger.error(f"分析 {coin} 失败，准备重试: {exc}")
        raise self.retry(exc=exc)
    finally:
        loop.close()

@celery_app.task(name="tasks.batch_crypto_sentiment_analysis", bind=True, max_retries=2)
def batch_crypto_sentiment_analysis(self, coins: List[str], days: int = 7):
    """批量分析多个币种（推荐用于仪表盘）"""
    if not coins or len(coins) > 10:
        raise ValueError("批量币种数量应在 1-10 个之间")
    
    results = []
    for coin in coins:
        try:
            # 在 Celery Worker 中直接调用另一个任务函数时，不会走队列，而是同步执行
            # 如果想完全并行，应该使用 Celery 的 group 或 chord 机制
            task_result = crypto_sentiment_analysis(coin, days)
            results.append(task_result)
        except Exception as e:
            logger.warning(f"批量中 {coin} 分析失败: {e}")
            results.append({"coin": coin, "error": str(e)})
    
    return {"total": len(coins), "results": results}
