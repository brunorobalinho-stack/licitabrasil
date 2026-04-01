"""Schemas de alerta."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class AlertaCreate(BaseModel):
    """Criação de alerta de monitoramento."""

    palavras_chave: list[str] | None = None
    modalidades: list[str] | None = None
    esferas: list[str] | None = None
    estados: list[str] | None = None
    municipios: list[str] | None = None
    valor_minimo: Decimal | None = None
    valor_maximo: Decimal | None = None
    frequencia: str = "DIARIO"


class AlertaRead(BaseModel):
    """Leitura de alerta."""

    model_config = {"from_attributes": True}

    id: int
    usuario_id: int
    palavras_chave: list[str] | None = None
    modalidades: list[str] | None = None
    esferas: list[str] | None = None
    estados: list[str] | None = None
    valor_minimo: Decimal | None = None
    valor_maximo: Decimal | None = None
    ativo: bool
    frequencia: str
    total_enviados: int
    criado_em: datetime
