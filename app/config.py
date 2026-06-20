from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AetherCrawler"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = "分布式AI加密货币情绪分析平台"

    # Database (PostgreSQL)
    # 默认使用 asyncpg 驱动实现异步操作
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/aethercrawler"

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"

    # OpenAI API / 大模型兼容接口
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL_NAME: str = "gpt-4o-mini"

    # CoinGecko API
    COINGECKO_API_BASE: str = "https://api.coingecko.com/api/v3"

    # Playwright 爬虫配置
    PLAYWRIGHT_HEADLESS: bool = True
    
    # NewsAPI 配置 (用于替代不稳定的 Playwright 爬虫)
    NEWS_API_KEY: str = ""
    NEWS_API_DAILY_LIMIT: int = 80  # 每天最大请求次数
    
    # HTTP 代理配置 (用于爬虫访问外网)
    HTTP_PROXY: str = ""
    HTTPS_PROXY: str = ""
    
    # HTTP 请求超时时间 (秒)
    HTTP_TIMEOUT: int = 30

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
