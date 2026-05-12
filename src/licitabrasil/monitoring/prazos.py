"""Coleta unificada de prazos críticos de todas as fontes de scrapers.

Lê os SQLite locais de cada scraper registrado em ``licitabrasil.scrapers.registry``
e produz um relatório classificado por urgência:

* **CRITICO** — prazo nas próximas 24 horas
* **ATENCAO** — prazo entre 1 e 7 dias
* **PLANEJAMENTO** — prazo entre 8 e 30 dias

Uso programático::

    from licitabrasil.monitoring import coletar_prazos, formatar_briefing
    prazos = coletar_prazos(dias=30)
    print(formatar_briefing(prazos))

Uso via CLI::

    licitabrasil monitor prazos --dias 30
    licitabrasil monitor prazos --argus  # só fontes com tag cliente-argus
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Iterable, Optional

from licitabrasil.scrapers.registry import (
    ScraperInfo,
    filter_by,
    list_scrapers,
)


class Urgencia(str, Enum):
    CRITICO = "CRITICO"      # ≤ 24h
    ATENCAO = "ATENCAO"      # 1 a 7 dias
    PLANEJAMENTO = "PLANEJAMENTO"  # 8 a 30 dias
    VENCIDO = "VENCIDO"      # já passou (mantemos pra auditoria)


@dataclass
class PrazoItem:
    fonte: str             # nome do scraper (ex: 'peintegrado')
    identificador: str     # numero/sde/processo
    objeto: str
    orgao: str
    modalidade: str
    fase_ou_situacao: str
    prazo: datetime
    url: str = ""
    urgencia: Urgencia = Urgencia.PLANEJAMENTO
    extra: dict = field(default_factory=dict)

    @property
    def horas_restantes(self) -> float:
        return (self.prazo - datetime.now()).total_seconds() / 3600

    @property
    def dias_restantes(self) -> int:
        return int((self.prazo.date() - datetime.now().date()).days)


# ── Cada scraper expõe a tabela `licitacoes` com schemas ligeiramente diferentes.
#    Esse mapping isola as diferenças.

@dataclass
class FonteQuery:
    """Mapeamento de colunas por scraper."""

    table: str = "licitacoes"
    col_id: str = "numero"
    col_objeto: str = "objeto"
    col_orgao: str = "orgao_sigla"
    col_modalidade: str = "modalidade"
    col_situacao: str = "situacao"
    col_prazo: str = "data_encerramento_propostas"
    col_url: str = "url_processo"


FONTE_QUERIES: dict[str, FonteQuery] = {
    # Esquema padrão (PE-Integrado)
    "peintegrado": FonteQuery(),
    # FIEMG
    "fiemg": FonteQuery(
        col_id="sde",
        col_orgao="unidade_compradora",
        col_situacao="fase",
        col_modalidade="categoria",
    ),
    # CBTU (schema legado — sem data de encerramento)
    "cbtu": FonteQuery(
        col_id="numero_processo",
        col_objeto="titulo",
        col_orgao="unidade_nome",
        col_modalidade="modalidade",
        col_situacao="status",
        col_prazo="data_modificacao",
        col_url="url_processo",
    ),
    # JFPE
    "jfpe": FonteQuery(
        col_id="numero",
        col_objeto="objeto",
        col_orgao="modalidade",      # JFPE não tem coluna 'orgao'
        col_modalidade="modalidade",
        col_situacao="modalidade",   # idem (placeholder)
        col_prazo="data_abertura",
        col_url="numero",            # idem
    ),
    # Maceió
    "maceio": FonteQuery(
        col_id="num_processo",
        col_objeto="objeto",
        col_orgao="orgao_nome",
        col_modalidade="modalidade",
        col_situacao="status",
        col_prazo="data_fechamento",
        col_url="num_processo",
    ),
    # Central Natal
    "central-natal": FonteQuery(
        col_id="numero_licitacao",
        col_objeto="objeto",
        col_orgao="orgao",
        col_modalidade="modalidade",
        col_situacao="status",
        col_prazo="data_abertura",
        col_url="url_detalhe",
    ),
    # Portal Compras CE
    "portalcompras-ce": FonteQuery(
        col_id="numero_processo",
        col_objeto="objeto",
        col_orgao="orgao",
        col_modalidade="tipo_aquisicao",
        col_situacao="status",
        col_prazo="data_abertura",
        col_url="numero_publicacao",
    ),
    # Prefeitura SP
    "prefeitura-sp": FonteQuery(
        col_id="numero_processo",
        col_objeto="objeto",
        col_orgao="orgao_nome",
        col_modalidade="modalidade",
        col_situacao="modo_disputa",
        col_prazo="data_encerramento",
        col_url="numero_controle_pncp",
    ),
}


def _classify(prazo: datetime, now: Optional[datetime] = None) -> Urgencia:
    now = now or datetime.now()
    delta = prazo - now
    if delta.total_seconds() < 0:
        return Urgencia.VENCIDO
    horas = delta.total_seconds() / 3600
    if horas <= 24:
        return Urgencia.CRITICO
    if horas <= 7 * 24:
        return Urgencia.ATENCAO
    return Urgencia.PLANEJAMENTO


def _parse_dt(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    # Normaliza: tira fuso, microssegundos
    text = value.split(".")[0].split("+")[0].strip()
    for fmt in (
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _coletar_fonte(info: ScraperInfo, dias: int, include_vencidos: bool) -> list[PrazoItem]:
    """Lê SQLite de um scraper e devolve PrazoItem dentro da janela."""
    if not info.db_path.exists():
        return []

    fq = FONTE_QUERIES.get(info.name, FonteQuery())

    horizon = (datetime.now() + timedelta(days=dias)).isoformat()
    floor = (datetime.now() - timedelta(days=1 if include_vencidos else 0)).isoformat()

    sql = f"""
        SELECT {fq.col_id} AS ident,
               {fq.col_objeto} AS objeto,
               {fq.col_orgao} AS orgao,
               {fq.col_modalidade} AS modalidade,
               {fq.col_situacao} AS situacao,
               {fq.col_prazo} AS prazo,
               {fq.col_url} AS url
        FROM {fq.table}
        WHERE {fq.col_prazo} IS NOT NULL
          AND datetime({fq.col_prazo}) >= datetime(?)
          AND datetime({fq.col_prazo}) <= datetime(?)
        ORDER BY datetime({fq.col_prazo}) ASC
    """

    out: list[PrazoItem] = []
    try:
        conn = sqlite3.connect(str(info.db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute(sql, (floor, horizon))
        for row in cur.fetchall():
            prazo_dt = _parse_dt(row["prazo"])
            if not prazo_dt:
                continue
            urgencia = _classify(prazo_dt)
            if urgencia == Urgencia.VENCIDO and not include_vencidos:
                continue
            out.append(
                PrazoItem(
                    fonte=info.name,
                    identificador=str(row["ident"]),
                    objeto=(row["objeto"] or "")[:200],
                    orgao=(row["orgao"] or ""),
                    modalidade=(row["modalidade"] or ""),
                    fase_ou_situacao=(row["situacao"] or ""),
                    prazo=prazo_dt,
                    url=(row["url"] or ""),
                    urgencia=urgencia,
                )
            )
        conn.close()
    except sqlite3.OperationalError:
        # Schema diferente — ignora silenciosamente
        return []

    return out


def coletar_prazos(
    dias: int = 30,
    fontes: Optional[Iterable[str]] = None,
    tag: Optional[str] = None,
    uf: Optional[str] = None,
    include_vencidos: bool = False,
) -> list[PrazoItem]:
    """Consolida prazos de todas as fontes filtradas, ordenados por prazo asc."""
    if fontes:
        scrapers = [s for s in list_scrapers() if s.name in fontes]
    else:
        scrapers = filter_by(tag=tag, uf=uf)

    todos: list[PrazoItem] = []
    for info in scrapers:
        todos.extend(_coletar_fonte(info, dias, include_vencidos))

    todos.sort(key=lambda p: p.prazo)
    return todos


# ── Formatação ──────────────────────────────────────────────────────────


URGENCIA_ORDER = [Urgencia.VENCIDO, Urgencia.CRITICO, Urgencia.ATENCAO, Urgencia.PLANEJAMENTO]
URGENCIA_LABEL = {
    Urgencia.VENCIDO: "VENCIDOS (últimas 24h)",
    Urgencia.CRITICO: "CRITICO (próximas 24h)",
    Urgencia.ATENCAO: "ATENCAO (1 a 7 dias)",
    Urgencia.PLANEJAMENTO: "PLANEJAMENTO (8 a 30 dias)",
}


def formatar_briefing(items: list[PrazoItem]) -> str:
    """Gera markdown estruturado por urgência."""
    if not items:
        return "_Nenhum prazo encontrado nas fontes consultadas._"

    por_urg: dict[Urgencia, list[PrazoItem]] = {u: [] for u in URGENCIA_ORDER}
    for it in items:
        por_urg[it.urgencia].append(it)

    linhas: list[str] = []
    linhas.append(f"# Briefing de Prazos — {datetime.now():%d/%m/%Y %H:%M}")
    linhas.append("")
    linhas.append(f"_Coletado de {len({i.fonte for i in items})} fonte(s), {len(items)} itens no horizonte._")
    linhas.append("")

    for urg in URGENCIA_ORDER:
        grupo = por_urg[urg]
        if not grupo:
            continue
        linhas.append(f"## {URGENCIA_LABEL[urg]} ({len(grupo)})")
        linhas.append("")
        for it in grupo:
            quando = it.prazo.strftime("%d/%m %H:%M")
            linhas.append(
                f"- **[{it.fonte}]** {it.identificador} — {it.objeto[:80]} "
                f"— prazo: **{quando}** — {it.fase_ou_situacao or it.modalidade}"
            )
        linhas.append("")

    return "\n".join(linhas)


def resumo_por_fonte(items: list[PrazoItem]) -> dict[str, dict[str, int]]:
    """Contagem por fonte × urgência (útil pra dashboards)."""
    out: dict[str, dict[str, int]] = {}
    for it in items:
        bucket = out.setdefault(it.fonte, {u.value: 0 for u in URGENCIA_ORDER})
        bucket[it.urgencia.value] += 1
    return out
