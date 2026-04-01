"""Schemas do dashboard."""

from __future__ import annotations

from pydantic import BaseModel

from licitabrasil.schemas.licitacao import LicitacaoResumo


class DashboardStats(BaseModel):
    total_licitacoes: int
    total_documentos: int
    total_fontes: int
    por_fonte: dict[str, int]
    recentes: list[LicitacaoResumo]
