"""Modelos Pydantic para licitacoes do Ceara."""

import hashlib
import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field


class LicitacaoCE(BaseModel):
    """Registro de licitacao do Portal de Compras CE."""

    # Identificacao
    numero_publicacao: str  # "2026/06297"
    numero_processo: str = ""
    numero_edital: str = ""
    viproc: Optional[str] = None
    id_pncp: Optional[str] = None

    # Orgao
    orgao: str = ""  # Unidade Compradora / Promotor
    gestor_compras: Optional[str] = None

    # Objeto
    objeto: str = ""

    # Classificacao
    sistematica: str = ""  # DISPENSA, PREGAO ELETRONICO, etc.
    forma_aquisicao: str = ""  # COTACAO ELETRONICA, etc.
    natureza_aquisicao: Optional[str] = None
    tipo_aquisicao: Optional[str] = None
    moeda: Optional[str] = None

    # Datas
    data_acolhimento: Optional[str] = None  # "04/03/2026 15:00"
    data_abertura: Optional[str] = None  # "09/03/2026 16:30"

    # Status
    status: str = ""

    # Resultado (do detalhe)
    vencedor: Optional[str] = None
    valor_lance: Optional[str] = None

    # Documentos (nomes)
    documentos: list[str] = []

    # Metadados
    fonte: str = "licitaweb_ce"
    url_detalhe: Optional[str] = None
    data_coleta: datetime = datetime.now()
    tem_detalhe: bool = False  # True se enriquecido via detail page

    @computed_field
    @property
    def hash_registro(self) -> str:
        data = {
            "numero_publicacao": self.numero_publicacao,
            "status": self.status,
            "objeto": self.objeto,
            "orgao": self.orgao,
            "vencedor": self.vencedor,
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()

    @property
    def ano(self) -> int:
        try:
            return int(self.numero_publicacao.split("/")[0])
        except (ValueError, IndexError):
            return 0

    @property
    def sequencial(self) -> int:
        try:
            return int(self.numero_publicacao.split("/")[1])
        except (ValueError, IndexError):
            return 0
