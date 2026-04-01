"""Schemas de perfil de empresa."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class PerfilEmpresaCreate(BaseModel):
    """Criação/atualização de perfil."""

    cnpj: str
    razao_social: str
    cnaes: list[str] | None = None
    palavras_chave: list[str] | None = None
    valor_minimo: Decimal | None = None
    valor_maximo: Decimal | None = None
    estados: list[str] | None = None
    municipios: list[str] | None = None
    modalidades: list[str] | None = None
    endereco: str | None = None
    telefone: str | None = None
    email: str | None = None
    representante_legal: str | None = None


class PerfilEmpresaRead(BaseModel):
    """Leitura de perfil."""

    model_config = {"from_attributes": True}

    id: str
    cnpj: str
    razao_social: str
    cnaes: list[str] | None = None
    palavras_chave: list[str] | None = None
    valor_minimo: Decimal | None = None
    valor_maximo: Decimal | None = None
    estados: list[str] | None = None
    municipios: list[str] | None = None
    modalidades: list[str] | None = None
    criado_em: datetime
    atualizado_em: datetime
