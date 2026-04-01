"""Configuração do scraper da Prefeitura de SP."""

from pathlib import Path

from pydantic_settings import BaseSettings


# 13 modalidades de contratação no PNCP
MODALIDADES = {
    1: "Leilão - Loss",
    2: "Diálogo Competitivo",
    3: "Concurso",
    4: "Concorrência - Eletrônica",
    5: "Concorrência - Presencial",
    6: "Pregão - Eletrônico",
    7: "Pregão - Presencial",
    8: "Dispensa de Licitação",
    9: "Inexigibilidade",
    10: "Manifestação de Interesse",
    11: "Pré-qualificação",
    12: "Credenciamento",
    13: "Leilão - Eletrônico",
}

# IBGE code para São Paulo capital
IBGE_SAO_PAULO = "3550308"


class Settings(BaseSettings):
    base_url: str = "https://pncp.gov.br/api/consulta"
    ibge_municipio: str = IBGE_SAO_PAULO
    uf: str = "SP"

    # Rate limiting
    max_concurrent: int = 3
    delay_seconds: float = 1.0
    request_timeout: int = 30
    max_retries: int = 3

    # Defaults
    default_days: int = 7
    page_size: int = 50

    # Paths
    data_dir: Path = Path("./data/prefeitura_sp")

    user_agent: str = "LicitaBrasil/1.0 (+https://github.com/brunorobalinho-stack/licitabrasil)"

    model_config = {"env_file": ".env", "env_prefix": "PREFSP_", "env_file_encoding": "utf-8"}

    @property
    def db_path(self) -> Path:
        return self.data_dir / "prefeitura_sp.db"

    @property
    def api_url(self) -> str:
        return f"{self.base_url}/v1/contratacoes/publicacao"
