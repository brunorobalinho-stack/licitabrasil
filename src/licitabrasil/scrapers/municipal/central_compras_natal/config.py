"""Configuracoes do scraper da Central de Compras de Natal/RN."""

from pathlib import Path

from pydantic_settings import BaseSettings


MODALIDADES = {
    "pregao-eletronico": "Pregão Eletrônico",
    "pregao-presencial": "Pregão Presencial",
    "concorrencia": "Concorrência",
    "tomada-precos": "Tomada de Preços",
    "dispensa-licitacao": "Dispensa de Licitação",
    "inexigibilidade": "Inexigibilidade",
    "ata-registro-precos": "Ata de Registro de Preços",
}


class Settings(BaseSettings):
    # URLs
    base_url: str = "https://centraldecompras.natal.rn.gov.br"
    listing_path: str = "/paginas/licitacoes/consulta/"

    # Rate limiting
    max_concurrent: int = 3
    delay_seconds: float = 1.0
    request_timeout: int = 60
    max_retries: int = 3

    # Paths
    data_dir: Path = Path("./data/central_compras_natal")
    db_path: Path = Path("./data/central_compras_natal/licitacoes_natal.db")

    # User-Agent
    user_agent: str = "LicitaBrasil/1.0 (+https://github.com/brunorobalinho-stack/licitabrasil)"

    # SSL
    verify_ssl: bool = True

    model_config = {"env_file": ".env", "env_prefix": "NATAL_", "env_file_encoding": "utf-8"}

    @property
    def listing_url(self) -> str:
        return f"{self.base_url}{self.listing_path}"

    def detail_url(self, mod: str, record_id: int) -> str:
        return f"{self.listing_url}?mod={mod}&id={record_id}"
