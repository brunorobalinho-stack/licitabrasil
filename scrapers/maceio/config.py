"""Configurações do scraper de Maceió."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Base URLs
    base_url: str = "https://www.licitacao.maceio.al.gov.br"
    api_base: str = "https://www.licitacao.maceio.al.gov.br/dados-abertos/licitacoes"

    # Rate limiting
    max_concurrent: int = 3
    delay_seconds: float = 1.0
    request_timeout: int = 30
    max_retries: int = 3

    # Paths
    data_dir: Path = Path("./data/maceio")
    db_path: Path = Path("./data/maceio/maceio.db")
    docs_dir: Path = Path("./data/maceio/documentos")

    # User-Agent
    user_agent: str = "LicitaBrasil/1.0 (+https://github.com/brunorobalinho-stack/licitabrasil)"

    # Keywords for alerts
    keywords: str = ""

    model_config = {"env_file": ".env", "env_prefix": "MACEIO_", "env_file_encoding": "utf-8"}

    @property
    def keywords_list(self) -> list[str]:
        if not self.keywords:
            return []
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]

    @property
    def listing_url(self) -> str:
        return self.base_url

    def detail_api_url(self, licitacao_id: int) -> str:
        return f"{self.api_base}/{licitacao_id}"

    def listing_page_url(self, page: int) -> str:
        return f"{self.base_url}?page={page}"
