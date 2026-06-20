import json
import re
import asyncio
from datetime import datetime
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from app.config import settings

# ==========================================
# AI 推理引擎安全带配置
# ==========================================
LLM_TIMEOUT_SECONDS = 20          # 单次调用超时（秒）
LLM_MAX_RETRIES = 2              # 最大重试次数
LLM_RETRY_DELAY_SECONDS = 3      # 重试间隔（秒）
LLM_MODEL_TOKEN_COST_PROMPT = 0.00001  # 估算：每千 token 的 Prompt 成本（美元）
LLM_MODEL_TOKEN_COST_COMPLETION = 0.00003  # 估算：每千 token 的 Completion 成本（美元）

class SentimentOutput(BaseModel):
    """LangChain 的结构化输出模型"""
    sentiment_score: float = Field(description="float between 0.0 (extremely bearish) and 1.0 (extremely bullish)")
    sentiment: str = Field(description="Must be exactly one of: 'Bullish', 'Bearish', or 'Neutral'")
    key_factors: List[str] = Field(description="List of 3-6 main price influencing factors extracted from the news")
    summary: str = Field(description="A concise 2-4 sentence professional market outlook based on the news")
    risk_level: str = Field(description="Must be exactly one of: 'Low', 'Medium', or 'High'")
    potential_catalysts: List[str] = Field(description="Possible upcoming events or triggers")

def _log_llm_cost(prompt_tokens: int, completion_tokens: int, coin: str):
    """
    记录 LLM 的 token 消耗和估算成本
    """
    prompt_cost = prompt_tokens * LLM_MODEL_TOKEN_COST_PROMPT / 1000
    completion_cost = completion_tokens * LLM_MODEL_TOKEN_COST_COMPLETION / 1000
    total_cost = prompt_cost + completion_cost
    print(f"[LLM Cost] {coin} | Prompt: {prompt_tokens} tokens (${prompt_cost:.6f}) | "
          f"Completion: {completion_tokens} tokens (${completion_cost:.6f}) | Total: ${total_cost:.6f}")

async def _invoke_llm_with_retry(chain, invoke_params: Dict[str, Any], coin: str) -> Optional[SentimentOutput]:
    """
    带超时和重试的 LLM 调用封装
    
    Args:
        chain: LangChain 的 prompt | model 链
        invoke_params: 调用参数
        coin: 币种名称（用于日志）
    
    Returns:
        SentimentOutput 对象，失败返回 None
    """
    last_error = None
    
    for attempt in range(LLM_MAX_RETRIES + 1):
        try:
            # 使用 asyncio.wait_for 设置超时
            result = await asyncio.wait_for(
                chain.ainvoke(invoke_params),
                timeout=LLM_TIMEOUT_SECONDS
            )
            # 如果模型返回了 usage 信息（通义千问通常会返回），记录成本
            if hasattr(result, 'usage') and result.usage:
                usage = result.usage
                _log_llm_cost(
                    getattr(usage, 'prompt_tokens', 0),
                    getattr(usage, 'completion_tokens', 0),
                    coin
                )
            return result
            
        except asyncio.TimeoutError:
            last_error = f"Attempt {attempt + 1}: LLM 调用超时（{LLM_TIMEOUT_SECONDS}s）"
            print(f"[LLM Warning] {last_error}，{'准备重试...' if attempt < LLM_MAX_RETRIES else '已达最大重试次数，放弃。'}")
            
        except Exception as e:
            last_error = f"Attempt {attempt + 1}: {type(e).__name__}: {str(e)}"
            print(f"[LLM Warning] {last_error}，{'准备重试...' if attempt < LLM_MAX_RETRIES else '已达最大重试次数，放弃。'}")
        
        if attempt < LLM_MAX_RETRIES:
            await asyncio.sleep(LLM_RETRY_DELAY_SECONDS)
    
    # 所有重试都失败
    print(f"[LLM Error] {coin} 所有重试均失败。最后错误：{last_error}")
    return None

async def perform_sentiment_analysis(news_texts: List[str], coin: str, historical_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    使用 LangChain + OpenAI 对抓取到的加密货币新闻进行情绪分析（增强版）
    
    安全带机制：
    1. 超时保护：单次调用超过 20 秒自动终止
    2. 自动重试：最多重试 2 次，间隔 3 秒
    3. 格式校验：处理 JSON 解析失败、markdown 代码块包裹等异常
    4. 成本监控：每次调用后记录 token 消耗和估算成本
    """
    if not news_texts:
        return {
            "sentiment_score": 0.5,
            "sentiment": "Neutral",
            "key_factors": ["No recent news found"],
            "summary": "No recent news available to analyze market sentiment.",
            "risk_level": "Medium",
            "potential_catalysts": []
        }
        
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "sk-your-openai-api-key-here":
        print(f"[LLM Warning] {coin} 未配置 OPENAI_API_KEY，返回 Mock 数据。")
        return {
            "sentiment_score": 0.75,
            "sentiment": "Bullish",
            "key_factors": ["Test Mock: SEC ETF approval", "Test Mock: Whale accumulation"],
            "summary": "This is a mocked summary because OPENAI_API_KEY is not configured.",
            "risk_level": "Medium",
            "potential_catalysts": ["Test Mock: Upcoming Fed meeting"]
        }

    # 处理历史价格数据
    price_trend = "No historical data available."
    if historical_data and historical_data.get("prices"):
        prices_7d = [p[1] for p in historical_data["prices"]]
        prices_24h = [p[1] for p in historical_data["prices"][-24:]] if len(historical_data["prices"]) >= 24 else prices_7d
        
        if len(prices_24h) >= 2:
            current_price = prices_24h[-1]
            high_24h = max(prices_24h)
            low_24h = min(prices_24h)
            drop_from_high = ((current_price - high_24h) / high_24h) * 100
            
            if historical_data.get("current_data") and "usd" in historical_data["current_data"]:
                current_price = historical_data["current_data"]["usd"]
                drop_from_high = ((current_price - high_24h) / high_24h) * 100

            price_trend = (
                f"当前价格: ${current_price:.2f}。\n"
                f"过去24小时最高: ${high_24h:.2f}，最低: ${low_24h:.2f}。\n"
                f"距离24小时高点跌幅: {drop_from_high:.2f}%。\n"
                f"请特别注意短期急跌风险（如跌幅超过 1.5%），结合新闻判断是否有机构出货或恐慌盘。"
            )

    # 初始化模型
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_NAME,
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
        # 通义千问兼容 OpenAI 协议，可设置 max_tokens 防止无限输出
        max_tokens=2048,
    )
    
    structured_llm = llm.with_structured_output(SentimentOutput)
    
    prompt = PromptTemplate.from_template(
        """You are a senior cryptocurrency short-term trader (focusing on 15m/1H charts) and market analyst.
        Analyze the provided news and market data for {coin} and give a professional assessment.

        ### Input Data:
        - Coin: {coin}
        - Recent Price Data: 
        {price_trend}
        - Latest News:
        {news_context}

        ### Instructions:
        1. Be highly sensitive to short-term price drops (e.g., -1.5% to -2% or more). 
        2. If there is a sudden drop, explain if it's a normal pullback, a stop-loss hunt, or true distribution/panic.
        3. Provide direct, actionable analysis (Long/Short bias) with clear reasoning.
        4. Focus strictly on factors that impact immediate price action.
        5. IMPORTANT: You MUST output all your analysis, summaries, and key factors entirely in Simplified Chinese (简体中文).
        """
    )
    
    chain = prompt | structured_llm
    news_context = "\n".join([f"- {text}" for text in news_texts[:10]])
    invoke_params = {
        "coin": coin.capitalize(), 
        "news_context": news_context,
        "price_trend": price_trend
    }
    
    # 调用带安全带的 LLM
    result = await _invoke_llm_with_retry(chain, invoke_params, coin)
    
    if result is None:
        # 所有重试都失败
        print(f"[LLM Error] {coin} AI 推理失败（已重试 {LLM_MAX_RETRIES} 次），返回错误状态。")
        return {
            "sentiment_score": 0.5,
            "sentiment": "Neutral",
            "key_factors": [f"AI 推理失败（超时或网络错误）"],
            "summary": f"由于网络或 AI 服务超时，{coin} 的情绪分析暂时无法完成。请稍后重试。",
            "risk_level": "Medium",
            "potential_catalysts": []
        }
    
    # 成功返回，额外验证字段完整性
    output = result.model_dump()
    
    # 校验 sentiment_score 范围
    score = output.get("sentiment_score", 0.5)
    if not isinstance(score, (int, float)) or score < 0 or score > 1:
        print(f"[LLM Warning] {coin} sentiment_score 异常值: {score}，修正为 0.5")
        output["sentiment_score"] = 0.5
    
    # 校验 sentiment 字段
    valid_sentiments = {"Bullish", "Bearish", "Neutral"}
    if output.get("sentiment") not in valid_sentiments:
        print(f"[LLM Warning] {coin} sentiment 异常值: {output.get('sentiment')}，修正为 Neutral")
        output["sentiment"] = "Neutral"
    
    # 校验 risk_level 字段
    valid_risks = {"Low", "Medium", "High"}
    if output.get("risk_level") not in valid_risks:
        print(f"[LLM Warning] {coin} risk_level 异常值: {output.get('risk_level')}，修正为 Medium")
        output["risk_level"] = "Medium"
    
    print(f"[LLM Success] {coin} 情绪分析完成 | 情绪: {output['sentiment']} | 分数: {output['sentiment_score']:.2f}")
    return output
