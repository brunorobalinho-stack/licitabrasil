"""Modelos Pydantic para licitações FIEMG."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# Padrão SDE: "SDE 2026001650", "SDE-2026001650", "2026001650"
SDE_REGEX = re.compile(r"\bSDE[\s\-]*?(\d{10})\b", re.IGNORECASE)
SDE_BARE_REGEX = re.compile(r"\b(\d{10})\b")


def extract_sdes(text: str) -> list[str]:
    """Extrai todos os números SDE de um texto livre.

    Útil para parsear e-mails de notificação (licitacoes.compras@fiemg.com.br).
    Retorna na forma 'SDE-YYYYNNNNNN'.
    """
    matches = SDE_REGEX.findall(text)
    if not matches:
        # Heurística: 10 dígitos começando com ano
        for candidate in SDE_BARE_REGEX.findall(text):
            year = int(candidate[:4])
            if 2020 <= year <= 2030:
                matches.append(candidate)
    return list(dict.fromkeys(f"SDE-{m}" for m in matches))


def parse_sde(sde: str) -> dict[str, str]:
    """Extrai partes de um número SDE.

    Exemplo: ``SDE-2026001650`` →
        {"ano": "2026", "sequencia": "001650"}
    """
    sde_only = sde.replace("SDE-", "").replace("SDE ", "").strip()
    if len(sde_only) == 10:
        return {"ano": sde_only[:4], "sequencia": sde_only[4:], "raw": sde}
    return {"raw": sde}


# Fases conhecidas pelos e-mails:
# - "Fase de Cadastro"
# - "Fase de Proposta"
# - "Fase de Disputa"
# - "Fase de Aceitação"
# - "Em Negociação"
# - "Homologado"
# - "Encerrado"
FASE_NORMALIZADAS = {
    "cadastro": "Cadastro",
    "proposta": "Envio de Propostas",
    "envio": "Envio de Propostas",
    "disputa": "Disputa",
    "aceitação": "Aceitação",
    "aceitacao": "Aceitação",
    "negociação": "Negociação",
    "negociacao": "Negociação",
    "homologa": "Homologado",
    "encerr": "Encerrado",
    "suspens": "Suspenso",
    "deserto": "Deserto",
    "fracassado": "Fracassado",
    "cancelado": "Cancelado",
}


def normalize_fase(text: str) -> str:
    """Normaliza descrição de fase para vocabulário controlado."""
    low = text.lower()
    for key, value in FASE_NORMALIZADAS.items():
        if key in low:
            return value
    return text.strip()


class Licitacao(BaseModel):
    """Modelo principal de uma licitação FIEMG."""

    sde: str  # "SDE-2026001650"
    ano: int = 0
    sequencia: str = ""

    objeto: str = ""
    objeto_resumido: str = ""
    categoria: str = ""

    valor_estimado: Optional[float] = None
    valor_referencia: Optional[float] = None

    data_publicacao: Optional[datetime] = None
    data_abertura_propostas: Optional[datetime] = None
    data_encerramento_propostas: Optional[datetime] = None
    data_sessao_publica: Optional[datetime] = None

    fase: str = ""
    situacao: str = ""

    unidade_compradora: str = ""  # Empresa/Sistema FIEMG (SESI/SENAI/etc)
    cidade_entrega: str = ""

    url_processo: str = ""
    url_edital: Optional[str] = None
    urls_anexos: list[str] = Field(default_factory=list)

    motivo_justificativa: Optional[str] = None  # ex: "Ampliação de competitividade"

    data_coleta: datetime = Field(default_factory=datetime.now)

    @computed_field  # type: ignore[misc]
    @property
    def hash_registro(self) -> str:
        content = (
            f"{self.sde}|{self.objeto}|{self.fase}|{self.situacao}|"
            f"{self.data_encerramento_propostas}|{self.valor_estimado}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @classmethod
    def from_sde(cls, sde: str, **kwargs) -> "Licitacao":
        parts = parse_sde(sde)
        return cls(
            sde=sde if sde.startswith("SDE") else f"SDE-{sde}",
            ano=int(parts.get("ano", 0) or 0),
            sequencia=parts.get("sequencia", ""),
            **kwargs,
        )


class LicitacaoListItem(BaseModel):
    sde: str
    objeto_resumido: str = ""
    fase: str = ""
    data_encerramento_propostas: Optional[datetime] = None
    url: str = ""
