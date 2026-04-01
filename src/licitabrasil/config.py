"""Configuração centralizada via pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Lê variáveis do .env ou ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://licitabrasil:licitabrasil_dev@localhost:5432/licitabrasil"
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
