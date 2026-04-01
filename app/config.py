from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://licitabrasil:licitabrasil_dev@localhost:5432/licitabrasil"
    database_url_sync: str = "postgresql://licitabrasil:licitabrasil_dev@localhost:5432/licitabrasil"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24  # 24h
    app_name: str = "LicitaBrasil"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
