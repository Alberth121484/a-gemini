from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Slack
    slack_bot_token: str
    slack_app_token: str
    slack_signing_secret: str
    
    # Google Gemini
    google_api_key: str
    
    # OpenAI
    openai_api_key: str
    
    # Anthropic (optional)
    anthropic_api_key: Optional[str] = None
    
    # Tavily
    tavily_api_key: str
    
    # ConvertAPI
    convert_api_key: str
    
    # Database
    database_url: str
    database_pool_min: int = 10
    database_pool_max: int = 100
    
    # Redis (optional - works without it but no caching)
    redis_url: Optional[str] = None
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 4
    log_level: str = "INFO"
    
    # Rate Limiting
    rate_limit_requests: int = 100
    rate_limit_window: int = 60
    
    # Model Configuration
    default_model: str = "gemini-2.5-pro"
    image_model: str = "imagen-4.0-ultra-generate-preview-06-06"
    
    # Memory
    chat_history_table: str = "n8n_chat_histories_geminiv2"
    logs_table: str = "logsgemini"
    context_window_length: int = 3
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
