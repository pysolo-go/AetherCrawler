from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime

# ========================
# AnalysisResult Schemas
# ========================
class AnalysisResultBase(BaseModel):
    coin: str = Field(..., description="分析的加密货币名称")
    price_data: Dict[str, Any] = Field(..., description="来自 CoinGecko 的当前价格数据")
    historical_prices: Optional[List[List[float]]] = Field(default=[], description="历史价格图表数据")
    sentiment_score: float = Field(..., description="情绪分数")
    sentiment: str = Field(..., description="定性情绪: Bullish, Bearish, Neutral")
    key_factors: List[str] = Field(..., description="关键价格影响因素")
    summary: str = Field(..., description="综合分析总结")
    risk_level: Optional[str] = Field(default="Medium", description="风险等级: Low, Medium, High")
    potential_catalysts: Optional[List[str]] = Field(default=[], description="潜在催化剂列表")
    analysis_period_days: int = Field(default=7, description="分析涵盖的天数")

class AnalysisResultCreate(AnalysisResultBase):
    task_id: int

class AnalysisResultResponse(AnalysisResultBase):
    id: int
    task_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

# ========================
# Task Schemas
# ========================
class TaskCreate(BaseModel):
    coin: str = Field(default="bitcoin", description="要分析的加密货币ID (e.g. bitcoin, ethereum)")
    days: int = Field(default=7, description="分析涵盖的天数")

class TaskResponse(BaseModel):
    id: int
    celery_task_id: str
    coin: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None
    # 取消懒加载带来的 greenlet 报错：创建时暂不包含 result
    result: Optional[AnalysisResultResponse] = None

    model_config = ConfigDict(from_attributes=True)
