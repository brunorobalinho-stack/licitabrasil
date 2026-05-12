"""Configurações do scraper PE-Integrado."""

from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # URLs base do portal Compras de PE (SAD-PE / peintegrado)
    base_url: str = "https://www.peintegrado.pe.gov.br"

    # Endpoints reais (probe em 12/05/2026): ASP.NET WebForms com __doPostBack
    # ViewState. As páginas vêm sem linhas — dados carregados via postback.
    listing_andamento_path: str = "/Portal/Pages/LicitacoesEmAndamento.aspx"
    listing_dispensa_path: str = "/Portal/Pages/DispensaLicitacoes.aspx"
    listing_encerradas_path: str = "/Portal/Pages/LicitacoesEncerradas.aspx"

    # Detalhamento por número (rota a confirmar no postback inicial)
    detail_path: str = "/Portal/Pages/DetalheProcesso.aspx"
    # RSS / Atom feed (não localizado em probe — mantido por compatibilidade)
    feed_path: str = "/Portal/rss/editais.xml"

    # Compat com versão anterior do client.py
    @property
    def listing_path(self) -> str:
        return self.listing_andamento_path

    # Rate limiting & resiliência
    max_concurrent: int = 2
    delay_seconds: float = 1.5
    request_timeout: int = 30
    max_retries: int = 3

    # Paths
    data_dir: Path = Path("./data/peintegrado")
    db_path: Path = Path("./data/peintegrado/peintegrado.db")

    # User-Agent (alguns portais .gov bloqueiam UA padrão)
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    # Filtros padrão (override via env: PEINTEGRADO_KEYWORDS=...)
    keywords: str = ""  # ex: "limpeza,terceirizado,vigilância,bilhetagem"

    model_config = {
        "env_file": ".env",
        "env_prefix": "PEINTEGRADO_",
        "env_file_encoding": "utf-8",
    }

    @property
    def listing_url(self) -> str:
        return f"{self.base_url}{self.listing_path}"

    @property
    def feed_url(self) -> str:
        return f"{self.base_url}{self.feed_path}"

    def detail_url(self, processo: str) -> str:
        # PE-Integrado usa parâmetros JSF — o helper monta querystring básica
        return f"{self.base_url}{self.detail_path}?processo={processo}"

    @property
    def keywords_list(self) -> list[str]:
        if not self.keywords:
            return []
        return [k.strip().lower() for k in self.keywords.split(",") if k.strip()]
