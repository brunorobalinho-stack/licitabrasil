"""Configuracoes do scraper do Portal de Compras do Ceara."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # URLs
    licitaweb_base: str = "https://s2gpr.sefaz.ce.gov.br/licita-web"
    listing_url: str = "https://s2gpr.sefaz.ce.gov.br/licita-web/paginas/licita/PublicacaoList.seam"
    detail_url: str = "https://s2gpr.sefaz.ce.gov.br/licita-web/paginas/licita/Licitacao.seam"
    portal_url: str = "https://www.portalcompras.ce.gov.br"

    # Rate limiting
    max_concurrent: int = 2
    delay_seconds: float = 2.0
    request_timeout: int = 60
    max_retries: int = 3

    # Paths
    data_dir: Path = Path("./data/portalcompras_ce")
    db_path: Path = Path("./data/portalcompras_ce/licitacoes_ce.db")
    docs_dir: Path = Path("./data/portalcompras_ce/documentos")

    # User-Agent
    user_agent: str = "LicitaBrasil/1.0 (+https://github.com/brunorobalinho-stack/licitabrasil)"

    # SSL
    verify_ssl: bool = False

    model_config = {"env_file": ".env", "env_prefix": "CE_", "env_file_encoding": "utf-8"}

    def detail_page_url(self, publicacao: str) -> str:
        return f"{self.detail_url}?nuPublicacao={publicacao}"
