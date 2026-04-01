"""Modelos Pydantic para licitações de Maceió."""

import hashlib
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


class Orgao(BaseModel):
    nome: str
    sigla: str = ""


class Empresa(BaseModel):
    nome: str
    cnpj: str = ""
    enquadramento: str = ""
    tipo_societario: str = ""
    cidade: str = ""
    estado: str = ""


class Homologacao(BaseModel):
    data_publicacao_homologacao: Optional[datetime] = None
    data_publicacao_extrato: Optional[datetime] = None
    lotes: str = ""
    valor_estimado: float = 0.0
    valor_contratado: float = 0.0
    empresa: Optional[Empresa] = None
    arquivo: Optional[str] = None


class AtaRegistro(BaseModel):
    """Ata de registro de preço vinculada a uma licitação."""
    numero: str = ""
    data_assinatura: Optional[datetime] = None
    data_publicacao: Optional[datetime] = None
    vigencia_inicio: Optional[datetime] = None
    vigencia_fim: Optional[datetime] = None
    empresa: Optional[Empresa] = None
    arquivo: Optional[str] = None


class Documento(BaseModel):
    tipo: str
    descricao: str = ""
    criado_em: Optional[datetime] = None
    arquivo: str  # download URL
    sha256: Optional[str] = None  # filled after download
    local_path: Optional[str] = None  # local file path after download


class Licitacao(BaseModel):
    """Modelo principal de uma licitação de Maceió."""
    id: int  # internal site ID (from /visualizar/{id})
    num_processo: str
    objeto: str
    data_abertura: Optional[datetime] = None
    hora_abertura: str = ""
    data_fechamento: Optional[datetime] = None
    hora_fechamento: Optional[str] = None
    numero_modalidade: int = 0
    ano_modalidade: int = 0
    modalidade: str = ""
    orgao: Optional[Orgao] = None
    cota: str = ""
    status: str = ""
    responsavel: str = ""
    homologacoes: list[Homologacao] = Field(default_factory=list)
    atas: list[AtaRegistro] = Field(default_factory=list)
    documentos: list[Documento] = Field(default_factory=list)
    data_coleta: datetime = Field(default_factory=datetime.now)
    raw_json: Optional[str] = None  # raw API response for debugging

    @computed_field
    @property
    def hash_registro(self) -> str:
        content = (
            f"{self.num_processo}|{self.objeto}|{self.status}|"
            f"{len(self.homologacoes)}|{len(self.atas)}|{len(self.documentos)}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @computed_field
    @property
    def numero_formatado(self) -> str:
        if self.numero_modalidade and self.ano_modalidade:
            return f"{self.numero_modalidade}/{self.ano_modalidade}"
        return self.num_processo


class LicitacaoListItem(BaseModel):
    """Item da listagem HTML (antes de buscar detalhes via API)."""
    id: int
    numero: str = ""
    tipo: str = ""
    objeto: str = ""
    data_abertura: str = ""
    orgao: str = ""
    status: str = ""
