"""
飞书 Webhook 通知模块

功能：
- 发送加密货币情绪分析预警到飞书群
- 支持去重（同一币种同一信号 15 分钟内不重复推送）
- 支持紧急关闭（ENABLE_AUTO_NOTIFY=false 时静默跳过）

飞书机器人创建步骤：
1. 打开飞书群 → 设置 → 群机器人 → 添加机器人 → 自定义机器人
2. 设置机器人名称（如"AetherCrawler 预警"）
3. 获取 Webhook 地址，填入 .env 的 FEISHU_WEBHOOK_URL
"""

import json
import time
import httpx
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from app.config import settings

logger = logging.getLogger(__name__)

# 简单的内存缓存用于去重（生产环境建议用 Redis）
_last_alert_cache: Dict[str, float] = {}

def _should_send_alert(coin: str, sentiment: str) -> bool:
    """
    检查是否应该发送预警（去重逻辑）
    
    同一币种 + 同一信号（如 "Bearish"）在 FEISHU_DEDUP_WINDOW_MINUTES 内不重复推送
    """
    cache_key = f"{coin.lower()}_{sentiment.lower()}"
    current_time = time.time()
    
    last_sent_time = _last_alert_cache.get(cache_key, 0)
    time_since_last = current_time - last_sent_time
    
    if time_since_last < settings.FEISHU_DEDUP_WINDOW_MINUTES * 60:
        logger.info(f"[Feishu] 去重：{coin} {sentiment} 在 {settings.FEISHU_DEDUP_WINDOW_MINUTES} 分钟内已推送过，跳过")
        return False
    
    # 更新缓存
    _last_alert_cache[cache_key] = current_time
    return True

def _build_feishu_card(
    coin: str,
    sentiment_score: float,
    sentiment: str,
    summary: str,
    risk_level: str,
    price_info: Optional[Dict[str, Any]] = None,
    fear_and_greed: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    构建飞书消息卡片格式
    
    使用飞书的交互式卡片格式，美观且支持点击跳转
    """
    # 情绪颜色：绿涨红跌
    if sentiment.lower() in ["bullish", "看多"]:
        accent_color = "red"  # 飞书卡片用 hex 颜色
        sentiment_icon = "📈"
    elif sentiment.lower() in ["bearish", "看空"]:
        accent_color = "red"
        sentiment_icon = "📉"
    else:
        accent_color = "grey"
        sentiment_icon = "➡️"
    
    # 风险等级颜色
    risk_color = {
        "Low": "green",
        "Medium": "yellow", 
        "High": "red"
    }.get(risk_level, "grey")
    
    # 构造价格信息
    price_text = ""
    if price_info:
        price_text = f"当前价格: ${price_info.get('usd', 'N/A'):,.2f}"
        change_24h = price_info.get('usd_24h_change', 0)
        if change_24h is not None:
            emoji = "📈" if change_24h >= 0 else "📉"
            price_text += f" | 24H: {emoji} {change_24h:+.2f}%"
    
    # 构造恐惧贪婪指数
    fng_text = ""
    if fear_and_greed:
        fng_value = fear_and_greed.get('value', 'N/A')
        fng_class = fear_and_greed.get('value_classification', '')
        fng_text = f"恐惧贪婪指数: {fng_value} ({fng_class})"
    
    # AI 生成的人话总结
    ai_summary = summary[:200] + "..." if len(summary) > 200 else summary
    
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"{sentiment_icon} AetherCrawler 情绪预警 | {coin.upper()}"
                },
                "template": "red" if sentiment.lower() in ["bearish", "看空"] else "green"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**情绪信号**: {sentiment} ({sentiment_score:.2f})\n"
                                   f"**风险等级**: {risk_level}\n"
                                   f"{price_text}\n"
                                   f"{fng_text}"
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "div", 
                    "text": {
                        "tag": "lark_md",
                        "content": f"**AI 分析摘要**:\n{ai_summary}"
                    }
                },
                {"tag": "hr"},
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AetherCrawler"
                        }
                    ]
                }
            ],
            "actions": [
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {
                                "tag": "plain_text",
                                "content": "查看完整报告"
                            },
                            "type": "primary",
                            "url": "http://localhost:8000"
                        }
                    ]
                }
            ]
        }
    }
    
    return card

async def send_feishu_alert(
    coin: str,
    sentiment_score: float,
    sentiment: str,
    summary: str,
    risk_level: str,
    price_info: Optional[Dict[str, Any]] = None,
    fear_and_greed: Optional[Dict[str, Any]] = None
) -> bool:
    """
    发送飞书预警通知
    
    条件：
    - FEISHU_WEBHOOK_URL 已配置
    - ENABLE_AUTO_NOTIFY = True
    - sentiment_score < FEISHU_ALERT_THRESHOLD_LOW 或 > FEISHU_ALERT_THRESHOLD_HIGH
    - 同一币种同一信号在 15 分钟内未发送过
    
    Args:
        coin: 币种名称
        sentiment_score: 情绪分数 (0.0-1.0)
        sentiment: 情绪标签 (Bullish/Bearish/Neutral)
        summary: AI 生成的摘要
        risk_level: 风险等级 (Low/Medium/High)
        price_info: 价格信息字典
        fear_and_greed: 恐惧贪婪指数字典
    
    Returns:
        bool: 是否发送成功
    """
    # 1. 检查功能开关
    if not settings.ENABLE_AUTO_NOTIFY:
        logger.debug("[Feishu] 自动通知已关闭 (ENABLE_AUTO_NOTIFY=False)")
        return False
    
    # 2. 检查 Webhook URL
    if not settings.FEISHU_WEBHOOK_URL:
        logger.warning("[Feishu] 未配置 Webhook URL，跳过通知")
        return False
    
    # 3. 检查是否触发阈值
    if settings.FEISHU_ALERT_THRESHOLD_LOW <= sentiment_score <= settings.FEISHU_ALERT_THRESHOLD_HIGH:
        logger.debug(f"[Feishu] {coin} 情绪分数 {sentiment_score:.2f} 在阈值范围内，不发送预警")
        return False
    
    # 4. 去重检查
    if not _should_send_alert(coin, sentiment):
        return False
    
    # 5. 构建消息卡片
    card = _build_feishu_card(
        coin=coin,
        sentiment_score=sentiment_score,
        sentiment=sentiment,
        summary=summary,
        risk_level=risk_level,
        price_info=price_info,
        fear_and_greed=fear_and_greed
    )
    
    # 6. 发送请求
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                settings.FEISHU_WEBHOOK_URL,
                json=card
            )
            resp.raise_for_status()
            
        logger.info(f"[Feishu] 预警发送成功: {coin} {sentiment} ({sentiment_score:.2f})")
        return True
        
    except httpx.HTTPStatusError as e:
        logger.error(f"[Feishu] HTTP 错误: {e.response.status_code} - {e.response.text}")
        return False
    except Exception as e:
        logger.error(f"[Feishu] 发送失败: {type(e).__name__}: {str(e)}")
        return False

def send_failure_alert(coin: str, error_message: str) -> bool:
    """
    发送任务失败通知（同步版本，用于 Celery 任务失败回调）
    """
    if not settings.ENABLE_AUTO_NOTIFY or not settings.FEISHU_WEBHOOK_URL:
        return False
    
    card = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"⚠️ AetherCrawler 任务失败 | {coin.upper()}"
                },
                "template": "orange"
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**币种**: {coin.upper()}\n"
                                   f"**错误信息**: {error_message[:200]}\n"
                                   f"**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                }
            ]
        }
    }
    
    try:
        import requests
        resp = requests.post(settings.FEISHU_WEBHOOK_URL, json=card, timeout=10)
        resp.raise_for_status()
        logger.info(f"[Feishu] 失败通知发送成功: {coin}")
        return True
    except Exception as e:
        logger.error(f"[Feishu] 失败通知发送失败: {e}")
        return False
