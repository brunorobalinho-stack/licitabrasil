"""Schemas de licitação para API."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class LicitacaoRead(BaseModel):
    """Schema de leitura — retornado pela API."""

    model_config = {"from_attributes": True}

    id: int
    numero: str
    numero_original: str
    ano: int
    processo: str | None = None
    uasg: str | None = None
    modalidade: str
    status: str
    criterio_julgamento: str | None = None
    tipo_contratacao: str | None = None
    objeto: str
    objeto_resumido: str | None = None
    valor_estimado: Decimal | None = None
    valor_homologado: Decimal | None = None
    data_publicacao: datetime | None = None
    data_abertura: datetime | None = None
    data_encerramento: datetime | None = None
    data_homologacao: datetime | None = None
    exclusiva_me_epp: bool = False
    cota_reservada: bool = False
    portal_origem: str
    url_original: str
    url_edital: str | None = None
    orgao_id: int
    coletado_em: datetime
    atualizado_em: datetime
    score_relevancia: float | None = None


class LicitacaoResumo(BaseModel):
    """Schema resumido para listagens."""

    model_config = {"from_attributes": True}

    id: int
    objeto: str
    numero: str
    modalidade: str
    status: str
    valor_estimado: Decimal | None = None
    data_abertura: datetime | None = None
    portal_origem: str
    orgao_id: int


class LicitacaoCreate(BaseModel):
    """Schema de criação — entrada da API de ingestão."""

    numero: str
    numero_original: str
    ano: int
    processo: str | None = None
    uasg: str | None = None
    modalidade: str
    tipo_contratacao: str | None = None
    objeto: str
    valor_estimado: Decimal | None = None
    data_publicacao: datetime | None = None
    data_abertura: datetime | None = None
    status: str = "publicada"
    portal_origem: str
    url_original: str
    orgao_id: int
    hash_conteudo: str


class LicitacaoFilter(BaseModel):
    """Filtros de busca."""

    q: str | None = Field(None, description="Texto livre para busca no objeto")
    modalidade: str | None = None
    status: str | None = None
    portal_origem: str | None = None
    orgao_id: int | None = None
    valor_min: Decimal | None = None
    valor_max: Decimal | None = None
    data_inicio: datetime | None = None
    data_fim: datetime | None = None
    exclusiva_me_epp: bool | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
