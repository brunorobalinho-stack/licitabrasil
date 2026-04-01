"""Modelos Pydantic para licitacoes de Natal/RN."""

import hashlib
import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, computed_field


class DocumentoNatal(BaseModel):
    """Documento anexo a uma licitacao."""
    nome: str
    url: str
    responsavel: str = ""


class HistoricoNatal(BaseModel):
    """Fase do historico de uma licitacao."""
    data: str
    fase: str
    detalhe: str = ""
    arquivo_url: Optional[str] = None


class LicitanteNatal(BaseModel):
    """Licitante/empresa participante."""
    nome: str
    observacao: str = ""
    situacao: str = ""


class LicitacaoNatal(BaseModel):
    """Registro de licitacao da Central de Compras de Natal/RN."""

    # Identificacao
    numero_licitacao: str  # "91.004/2026"
    numero_processo: str = ""
    record_id: int = 0  # ID interno do site (param &id=)

    # Classificacao
    modalidade: str = ""  # "Pregão Eletrônico"
    modalidade_slug: str = ""  # "pregao-eletronico"
    tipo_licitacao: str = ""  # "Menor Preço"

    # Orgao
    orgao: str = ""  # Secretaria Licitante
    titulo: str = ""

    # Objeto
    objeto: str = ""

    # Datas
    data_publicacao: Optional[str] = None  # "24/02/2026"
    data_abertura: Optional[str] = None
    local_abertura: Optional[str] = None
    registro_preco: Optional[str] = None

    # Status (derivado do historico)
    status: str = ""

    # Detalhe
    documentos: list[DocumentoNatal] = []
    historico: list[HistoricoNatal] = []
    licitantes: list[LicitanteNatal] = []

    # Metadados
    fonte: str = "central_compras_natal"
    uf: str = "RN"
    municipio: str = "Natal"
    url_detalhe: Optional[str] = None
    data_coleta: datetime = datetime.now()
    tem_detalhe: bool = False

    @computed_field
    @property
    def hash_registro(self) -> str:
        data = {
            "numero_licitacao": self.numero_licitacao,
            "modalidade": self.modalidade,
            "objeto": self.objeto,
            "orgao": self.orgao,
            "status": self.status,
        }
        return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()
