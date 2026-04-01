import secrets

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://licitabrasil:licitabrasil_dev@localhost:5432/licitabrasil"
    database_url_sync: str = "postgresql://licitabrasil:licitabrasil_dev@localhost:5432/licitabrasil"
    redis_url: str = "redis://localhost:6379"
    secret_key: str = ""
    access_token_expire_minutes: int = 15
    app_name: str = "LicitaBrasil"
    debug: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @field_validator("secret_key", mode="before")
    @classmethod
    def _require_secret_key(cls, v: str) -> str:
        if not v:
            if True:  # substituir por check de env production futuramente
                return secrets.token_urlsafe(32)
            msg = "SECRET_KEY obrigatória em produção"
            raise ValueError(msg)
        return v


settings = Settings()
