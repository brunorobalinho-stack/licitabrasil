"""Configurações do scraper FIEMG."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    base_url: str = "https://licitacoes.compras.fiemg.com.br"

    # Endpoints conhecidos (validar com probe)
    listing_path: str = "/portal/processos-em-andamento"
    detail_path: str = "/portal/processo"
    feed_path: str = "/portal/rss/processos.xml"

    # Credenciais opcionais (FIEMG permite consulta sem login,
    # mas algumas categorias exigem cadastro)
    login: str = ""
    password: str = ""

    # Rate limiting
    max_concurrent: int = 2
    delay_seconds: float = 1.5
    request_timeout: int = 30
    max_retries: int = 3

    # Paths
    data_dir: Path = Path("./data/fiemg")
    db_path: Path = Path("./data/fiemg/fiemg.db")

    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    # Categorias de interesse (CNAEs / palavras-chave da Argus)
    keywords: str = ""

    model_config = {
        "env_file": ".env",
        "env_prefix": "FIEMG_",
        "env_file_encoding": "utf-8",
    }

    @property
    def listing_url(self) -> str:
        return f"{self.base_url}{self.listing_path}"

    @property
    def feed_url(self) -> str:
        return f"{self.base_url}{self.feed_path}"

    def detail_url(self, sde: str) -> str:
        return f"{self.base_url}{self.detail_path}/{sde}"

    @property
    def keywords_list(self) -> list[str]:
        if not self.keywords:
            return []
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]
