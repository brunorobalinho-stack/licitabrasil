from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "LicitaBrasil Backoffice"
    DEBUG: bool = False

    # Database (required - must be set via environment)
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/1"
    CACHE_TTL: int = 300  # 5 minutes

    # Auth (required - must be set via environment)
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8h workday

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:5174"]

    # Alerts
    SALARY_ALERT_DAYS_BEFORE: int = 5
    CONTRACT_ALERT_DAYS_BEFORE: int = 30

    class Config:
        env_file = ".env"
        env_prefix = "BACKOFFICE_"


@lru_cache
def get_settings() -> Settings:
    return Settings()
