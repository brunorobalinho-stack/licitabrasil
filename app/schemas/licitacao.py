from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LicitacaoRead(BaseModel):
    id: int
    numero_processo: str
    modalidade: Optional[str]
    objeto: str
    orgao: Optional[str]
    uf: Optional[str]
    status: Optional[str]
    data_publicacao: Optional[datetime]
    valor_estimado: Optional[float]
    fonte: str

    model_config = {"from_attributes": True}


class DashboardStats(BaseModel):
    total_licitacoes: int
    total_documentos: int
    total_fontes: int
    por_fonte: dict[str, int]
    recentes: list[LicitacaoRead]
