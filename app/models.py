from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Task(Base):
    """
    用于记录异步分析任务的状态和信息
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    celery_task_id = Column(String, unique=True, index=True, nullable=False, comment="Celery 分配的任务ID")
    coin = Column(String, index=True, nullable=False, comment="分析的加密货币名称，如 bitcoin")
    status = Column(String, default="PENDING", index=True, comment="任务状态：PENDING, STARTED, SUCCESS, FAILURE")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="任务创建时间")
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), comment="任务最后更新时间")

    # 一对一关联分析结果
    result = relationship("AnalysisResult", back_populates="task", uselist=False, cascade="all, delete-orphan")

class AnalysisResult(Base):
    """
    加密货币情绪分析的最终结果
    """
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), unique=True, nullable=False, comment="关联的任务ID")
    coin = Column(String, index=True, nullable=False, comment="加密货币名称")
    
    price_data = Column(JSON, nullable=False, comment="价格数据JSON：当前价格, 市值, 24h涨跌幅等")
    historical_prices = Column(JSON, nullable=True, comment="历史价格图表数据")
    sentiment_score = Column(Float, nullable=False, default=0.5, comment="情绪分数，例如 0.0 到 1.0 之间")
    sentiment = Column(String(255), nullable=False, default="Neutral", comment="整体情绪定性：Bullish / Bearish / Neutral")
    key_factors = Column(JSON, nullable=True, comment="关键价格影响因素列表，存储为 JSON 数组")
    summary = Column(Text, nullable=True, comment="分析总结报告")
    risk_level = Column(String(255), nullable=True, comment="风险等级: Low / Medium / High")
    potential_catalysts = Column(JSON, nullable=True, comment="潜在催化剂列表，存储为 JSON 数组")
    raw_news = Column(Text, nullable=True, comment="爬取到的原始新闻文本")
    analysis_period_days = Column(Integer, default=7, comment="分析所涵盖的历史天数")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), comment="分析完成时间")

    # 关联回 Task
    task = relationship("Task", back_populates="result")
