"""Modelos Pydantic para licitações do PE-Integrado."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, computed_field


# Modalidades reconhecidas no PE-Integrado (vistas nos e-mails da Argus)
MODALIDADE_MAP = {
    "CCD-DL": "Dispensa de Licitação (Compra Direta)",
    "CCD-IN": "Inexigibilidade (Compra Direta)",
    "NLCD-PE": "Pregão Eletrônico",
    "NLCD-CC": "Concorrência",
    "NLCD-CO": "Convite",
    "NLCD-TP": "Tomada de Preços",
    "AC": "Concurso / Acreditação",
}


def parse_processo_number(numero: str) -> dict[str, str]:
    """Extrai partes do número de processo do PE-Integrado.

    Exemplo: ``0290.2026.CCD.DL.0281.HR`` →
        {"sequencia": "0290", "ano": "2026", "tipo": "CCD",
         "sub": "DL", "edital": "0281", "orgao": "HR"}
    """
    parts = numero.strip().split(".")
    if len(parts) < 4:
        return {"raw": numero}
    return {
        "sequencia": parts[0],
        "ano": parts[1],
        "tipo": parts[2] if len(parts) > 2 else "",
        "sub": parts[3] if len(parts) > 3 else "",
        "edital": parts[4] if len(parts) > 4 else "",
        "orgao": ".".join(parts[5:]) if len(parts) > 5 else "",
        "raw": numero,
    }


def infer_modalidade(numero: str) -> str:
    """Mapeia o número de processo para modalidade legível."""
    parts = parse_processo_number(numero)
    key = f"{parts.get('tipo', '')}-{parts.get('sub', '')}"
    return MODALIDADE_MAP.get(key, f"Outro ({key})" if key != "-" else "Não identificada")


class Orgao(BaseModel):
    sigla: str = ""
    nome: str = ""


class LicitacaoListItem(BaseModel):
    """Item da listagem (antes do detalhamento)."""

    numero: str
    objeto_resumido: str = ""
    orgao_sigla: str = ""
    modalidade: str = ""
    situacao: str = ""
    url: str = ""


class Licitacao(BaseModel):
    """Modelo principal de uma licitação do PE-Integrado."""

    numero: str  # ex: 0290.2026.CCD.DL.0281.HR
    ano: int = 0
    sequencia: str = ""
    tipo: str = ""  # CCD, NLCD, AC
    sub_modalidade: str = ""  # DL, IN, PE, CC, CO, TP
    modalidade: str = ""  # texto legível
    orgao: Optional[Orgao] = None

    objeto: str = ""
    objeto_resumido: str = ""

    valor_estimado: Optional[float] = None
    valor_referencia: Optional[float] = None

    data_publicacao: Optional[datetime] = None
    data_abertura_propostas: Optional[datetime] = None
    data_encerramento_propostas: Optional[datetime] = None
    data_sessao_publica: Optional[datetime] = None

    situacao: str = ""  # "Em andamento", "Encerrada", "Suspensa", "Prorrogada"
    fase: str = ""

    url_processo: str = ""
    url_edital: Optional[str] = None
    urls_anexos: list[str] = Field(default_factory=list)

    cnpj_empresa_vencedora: Optional[str] = None
    razao_social_vencedora: Optional[str] = None

    data_coleta: datetime = Field(default_factory=datetime.now)
    raw_html: Optional[str] = None  # para debug; pode ficar None em produção

    @computed_field  # type: ignore[misc]
    @property
    def hash_registro(self) -> str:
        content = (
            f"{self.numero}|{self.objeto}|{self.situacao}|"
            f"{self.data_abertura_propostas}|{self.data_encerramento_propostas}|"
            f"{self.valor_estimado}"
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

    @computed_field  # type: ignore[misc]
    @property
    def numero_edital(self) -> str:
        parts = parse_processo_number(self.numero)
        return parts.get("edital", "")

    @classmethod
    def from_numero(cls, numero: str, **kwargs) -> "Licitacao":
        """Constrói uma Licitacao parseando o número do processo."""
        parts = parse_processo_number(numero)
        return cls(
            numero=numero,
            ano=int(parts.get("ano", 0) or 0),
            sequencia=parts.get("sequencia", ""),
            tipo=parts.get("tipo", ""),
            sub_modalidade=parts.get("sub", ""),
            modalidade=infer_modalidade(numero),
            orgao=Orgao(sigla=parts.get("orgao", "")),
            **kwargs,
        )


# ─────────────────────────────────────────────────────────────
# Regex utilitárias para parsing de e-mails de notificação do PE-Integrado
# ─────────────────────────────────────────────────────────────

# Padrão de número de processo nos e-mails do sistema:
# "0290.2026.CCD.DL.0281.HR" ou "0017.2026.NLCD.PE.0011.TJPE.FERM-PJ"
PROCESSO_REGEX = re.compile(
    r"\b(\d{3,4}\.\d{4}\.[A-Z]{2,5}\.[A-Z]{1,3}\.\d{3,5}\.[A-Z][A-Z0-9.\-_]+)\b"
)


def extract_processos(text: str) -> list[str]:
    """Extrai todos os números de processo PE-Integrado de um texto livre.

    Útil para parsear e-mails de notificação (sistema@peintegrado.pe.gov.br).
    """
    return list(dict.fromkeys(PROCESSO_REGEX.findall(text)))  # preserva ordem, dedup
