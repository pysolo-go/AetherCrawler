import json
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from app.config import settings

class SentimentOutput(BaseModel):
    """LangChain 的结构化输出模型"""
    sentiment_score: float = Field(description="float between 0.0 (extremely bearish) and 1.0 (extremely bullish)")
    sentiment: str = Field(description="Must be exactly one of: 'Bullish', 'Bearish', or 'Neutral'")
    key_factors: List[str] = Field(description="List of 3-6 main price influencing factors extracted from the news")
    summary: str = Field(description="A concise 2-4 sentence professional market outlook based on the news")
    risk_level: str = Field(description="Must be exactly one of: 'Low', 'Medium', or 'High'")
    potential_catalysts: List[str] = Field(description="Possible upcoming events or triggers")

async def perform_sentiment_analysis(news_texts: List[str], coin: str, historical_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    使用 LangChain + OpenAI 对抓取到的加密货币新闻进行情绪分析（增强版）
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
        # 防止未配置API Key时报错，直接返回 Mock 数据用于测试
        return {
            "sentiment_score": 0.75,
            "sentiment": "Bullish",
            "key_factors": ["Test Mock: SEC ETF approval", "Test Mock: Whale accumulation"],
            "summary": "This is a mocked summary because OPENAI_API_KEY is not configured.",
            "risk_level": "Medium",
            "potential_catalysts": ["Test Mock: Upcoming Fed meeting"]
        }

    # 处理历史价格数据（换回 CoinGecko 数据，同时保留对短期高低点的测算）
    price_trend = "No historical data available."
    if historical_data and historical_data.get("prices"):
        # 提取过去24小时（约24个数据点）和过去7天的数据
        prices_7d = [p[1] for p in historical_data["prices"]]
        prices_24h = [p[1] for p in historical_data["prices"][-24:]] if len(historical_data["prices"]) >= 24 else prices_7d
        
        if len(prices_24h) >= 2:
            current_price = prices_24h[-1]
            high_24h = max(prices_24h)
            low_24h = min(prices_24h)
            drop_from_high = ((current_price - high_24h) / high_24h) * 100
            
            # 使用最新的 current_data 里面的当前价（如果有的话）覆盖，更精准
            if historical_data.get("current_data") and "usd" in historical_data["current_data"]:
                current_price = historical_data["current_data"]["usd"]
                drop_from_high = ((current_price - high_24h) / high_24h) * 100

            price_trend = (
                f"当前价格: ${current_price:.2f}。\n"
                f"过去24小时最高: ${high_24h:.2f}，最低: ${low_24h:.2f}。\n"
                f"距离24小时高点跌幅: {drop_from_high:.2f}%。\n"
                f"请特别注意短期急跌风险（如跌幅超过 1.5%），结合新闻判断是否有机构出货或恐慌盘。"
            )

    # 初始化模型（支持通过配置接入通义千问等兼容 OpenAI 协议的大模型）
    llm = ChatOpenAI(
        model=settings.OPENAI_MODEL_NAME,
        temperature=0.3,
        api_key=settings.OPENAI_API_KEY,
        base_url=settings.OPENAI_BASE_URL,
    )
    
    # 将模型绑定结构化输出
    structured_llm = llm.with_structured_output(SentimentOutput)
    
    # 构造专业提示词
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
    
    # 组装 Chain
    chain = prompt | structured_llm
    
    news_context = "\n".join([f"- {text}" for text in news_texts[:10]])
    
    try:
        # 执行异步调用
        result = await chain.ainvoke({
            "coin": coin.capitalize(), 
            "news_context": news_context,
            "price_trend": price_trend
        })
        return result.model_dump()
    except Exception as e:
        print(f"Error in perform_sentiment_analysis: {e}")
        return {
            "sentiment_score": 0.5,
            "sentiment": "Neutral",
            "key_factors": [f"Analysis Error: {str(e)}"],
            "summary": "Failed to analyze sentiment due to an internal error.",
            "risk_level": "Medium",
            "potential_catalysts": []
        }
