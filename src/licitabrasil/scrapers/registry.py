"""Registry de scrapers disponíveis no LicitaBrasil.

Cada scraper é exposto como ``ScraperInfo`` com metadados e um módulo
executável (`python -m <module>`). O registry suporta:

- ``list_scrapers()`` — listagem dos scrapers registrados
- ``get_scraper(name)`` — busca por nome
- ``health_check(info)`` — request GET na URL base
- ``run_scraper(info, args)`` — executa via subprocess
- ``db_stats(info)`` — contagem de licitações no SQLite local

Adicionar novo scraper: definir o ``ScraperInfo`` e incluir em ``SCRAPERS``.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DATA_ROOT = PROJECT_ROOT / "data"


@dataclass(frozen=True)
class ScraperInfo:
    """Metadados de um scraper registrado."""

    name: str
    label: str
    esfera: str  # 'federal' | 'estadual' | 'municipal' | 'agregador'
    uf: str | None
    portal: str
    base_url: str
    module: str  # caminho do módulo executável (python -m <module>)
    db_relpath: str  # caminho relativo ao DATA_ROOT do SQLite gerado
    table_name: str = "licitacoes"
    description: str = ""
    tags: tuple[str, ...] = field(default_factory=tuple)
    enabled: bool = True  # False oculta de list_scrapers/filter_by por default; get_scraper(name) continua funcionando pra debug manual
    disabled_motivo: str = ""  # registro do POR QUE -- preenchido junto com enabled=False

    @property
    def db_path(self) -> Path:
        return DATA_ROOT / self.db_relpath


SCRAPERS: dict[str, ScraperInfo] = {
    "cbtu": ScraperInfo(
        name="cbtu",
        label="CBTU — Companhia Brasileira de Trens Urbanos",
        esfera="federal",
        uf=None,
        portal="gov.br/cbtu",
        base_url="https://www.gov.br/cbtu/pt-br/acesso-a-informacao/receitas-e-despesas/licitacoes",
        module="licitabrasil.scrapers.federal.cbtu_govbr",
        db_relpath="cbtu_govbr/cbtu_govbr.db",
        description=(
            "Scraping HTML do portal gov.br/cbtu (Plone CMS). "
            "Cobre Administração Central + STUs Recife, João Pessoa, Maceió e Natal."
        ),
        tags=("cliente-argus", "estatal", "ferroviario"),
    ),
    "jfpe": ScraperInfo(
        name="jfpe",
        label="JFPE — Justiça Federal de Pernambuco",
        esfera="federal",
        uf="PE",
        portal="jfpe.jus.br",
        base_url="https://www.jfpe.jus.br/index.php/transparencia/licitacoes",
        module="licitabrasil.scrapers.federal.jfpe",
        db_relpath="jfpe/jfpe.db",
        description=(
            "API REST do SCPA (apisapi.jfpe.jus.br/api/SCPA/). "
            "Lista licitações + empenhos + contratos + atas de registro."
        ),
        tags=("judiciario",),
    ),
    "comprasnet": ScraperInfo(
        name="comprasnet",
        label="ComprasNet / Compras.gov.br — Compras Federais",
        esfera="federal",
        uf=None,
        portal="compras.gov.br",
        base_url="https://compras.gov.br/",
        module="licitabrasil.scrapers.federal.comprasnet",
        db_relpath="comprasnet/comprasnet.db",
        description=(
            "Compras Federais Lei 8.666 e 14.133 (sucessor do ComprasNet). "
            "API oficial em dadosabertos.compras.gov.br complementa o PNCP "
            "pra fontes legadas Lei 8.666 nao agregadas. Pareado com PNCP "
            "(via prefeitura_sp) cobre o tronco federal do radar."
        ),
        tags=("federal", "alta-prioridade", "recon-pendente"),
        enabled=False,
        disabled_motivo=(
            "Reservado 15/05/2026: scraper nao existe ainda, modulo "
            "licitabrasil.scrapers.federal.comprasnet vazio. Flag fica "
            "registrada aqui pro proximo sprint -- aparece em list_scrapers "
            "como disabled. Caminho de implementacao previsto: "
            "(1) Recon da API dadosabertos.compras.gov.br (endpoints, "
            "pagination, rate limit, schema dos contratos / licitacoes / atas). "
            "(2) Decidir cobertura: full historico Lei 8.666 (volume grande) "
            "ou janela de N dias com refresh diario (recomendado pra MVP). "
            "(3) Codar httpx + Pydantic v2 seguindo o template do JFPE "
            "(API JSON, sem Playwright). (4) Storage SQLite padrao do projeto. "
            "Tempo estimado: 1 dia de recon + 2-3 dias de codigo + testes. "
            "Bruno marcou como flag pra proximo sprint -- nao Dia 0.5."
        ),
    ),
    "peintegrado": ScraperInfo(
        name="peintegrado",
        label="PE-Integrado — Portal de Compras de Pernambuco",
        esfera="estadual",
        uf="PE",
        portal="peintegrado.pe.gov.br",
        base_url="https://www.peintegrado.pe.gov.br/",
        module="licitabrasil.scrapers.estadual.peintegrado",
        db_relpath="peintegrado/peintegrado.db",
        description=(
            "Portal estadual de PE (SAD-PE). Cobre Compras Diretas (CCD), "
            "Pregões Eletrônicos, Concorrências e Inexigibilidades — onde "
            "a Argus recebe a maioria das notificações por e-mail."
        ),
        tags=("cliente-argus", "alta-prioridade"),
    ),
    "fiemg": ScraperInfo(
        name="fiemg",
        label="FIEMG Compras",
        esfera="agregador",
        uf="MG",
        portal="licitacoes.compras.fiemg.com.br",
        base_url="https://licitacoes.compras.fiemg.com.br/",
        module="licitabrasil.scrapers.agregadores.fiemg",
        db_relpath="fiemg/fiemg.db",
        description=(
            "Portal de Compras da FIEMG (Federação das Indústrias de MG). "
            "Processos identificados por SDE (10 dígitos). Argus recebe "
            "notificações por e-mail de prorrogações e reaberturas."
        ),
        tags=("cliente-argus", "privado"),
        enabled=False,
        disabled_motivo=(
            "Disabled 12/05/2026: base_url 'licitacoes.compras.fiemg.com.br' "
            "retorna NXDOMAIN no DNS público. Hostname provavelmente foi "
            "especulado durante desenho do scraper. URL real plausível: "
            "compras.fiemg.com.br (Cloudflare anti-bot ativo, exige Playwright). "
            "Pra reativar: confirmar URL real no browser, atualizar base_url, "
            "trocar client.py de httpx puro pra Playwright, retestar com probe."
        ),
    ),
    "portalcompras-ce": ScraperInfo(
        name="portalcompras-ce",
        label="Portal de Compras do Ceará (Licitaweb / S2GPR)",
        esfera="estadual",
        uf="CE",
        portal="portalcompras.ce.gov.br",
        base_url="https://s2gpr.sefaz.ce.gov.br/licita-web/",
        module="licitabrasil.scrapers.estadual.portalcompras_ce",
        db_relpath="portalcompras_ce/licitacoes_ce.db",
        description=(
            "Portal estadual com JSF + paginação server-side. "
            "Mantém checkpoint para retomar de onde parou."
        ),
        tags=("estado",),
    ),
    "central-natal": ScraperInfo(
        name="central-natal",
        label="Central de Compras de Natal/RN",
        esfera="municipal",
        uf="RN",
        portal="natal.rn.gov.br",
        base_url="https://www.natal.rn.gov.br/centraldecompras",
        module="licitabrasil.scrapers.municipal.central_compras_natal",
        db_relpath="central_compras_natal/licitacoes_natal.db",
        description="Central de Compras da Prefeitura de Natal.",
        tags=("municipio",),
    ),
    "maceio": ScraperInfo(
        name="maceio",
        label="Prefeitura de Maceió/AL",
        esfera="municipal",
        uf="AL",
        portal="maceio.al.gov.br",
        base_url="https://licitacao.maceio.al.gov.br/",
        module="licitabrasil.scrapers.municipal.maceio",
        db_relpath="maceio/maceio.db",
        description=(
            "Portal de Licitações da Prefeitura de Maceió. "
            "Coleta licitações + atas + homologações + documentos."
        ),
        tags=("municipio",),
    ),
    "prefeitura-sp": ScraperInfo(
        name="prefeitura-sp",
        label="Prefeitura de São Paulo/SP",
        esfera="municipal",
        uf="SP",
        portal="prefeitura.sp.gov.br",
        base_url="https://www.prefeitura.sp.gov.br/cidade/secretarias/gestao/coordenadoria_de_bens_e_servicos/index.php",
        module="licitabrasil.scrapers.municipal.prefeitura_sp",
        db_relpath="prefeitura_sp/prefeitura_sp.db",
        description="Portal de licitações da Prefeitura de São Paulo.",
        tags=("municipio",),
    ),
}


# ── Lookup helpers ──────────────────────────────────────────────────────


def list_scrapers(*, include_disabled: bool = False) -> list[ScraperInfo]:
    """Retorna lista ordenada por nome dos scrapers registrados.

    Por default oculta scrapers com ``enabled=False``. Use
    ``include_disabled=True`` pra ver tudo (debug / `scrape list --all`).
    """
    items = SCRAPERS.values()
    if not include_disabled:
        items = (s for s in items if s.enabled)
    return sorted(items, key=lambda s: s.name)


def list_scraper_names(*, include_disabled: bool = False) -> list[str]:
    """Compat: retorna apenas os nomes (interface antiga)."""
    if include_disabled:
        return sorted(SCRAPERS.keys())
    return sorted(name for name, s in SCRAPERS.items() if s.enabled)


def get_scraper(name: str) -> ScraperInfo:
    """Busca um scraper pelo nome, com erro descritivo se não existir."""
    if name not in SCRAPERS:
        available = ", ".join(sorted(SCRAPERS.keys()))
        raise ValueError(f"Scraper '{name}' não encontrado. Disponíveis: {available}")
    return SCRAPERS[name]


def filter_by(
    esfera: str | None = None,
    uf: str | None = None,
    tag: str | None = None,
    *,
    include_disabled: bool = False,
) -> list[ScraperInfo]:
    """Filtra scrapers por esfera, UF e/ou tag.

    Scrapers com ``enabled=False`` ficam fora por default; passe
    ``include_disabled=True`` pra incluir.
    """
    out = list_scrapers(include_disabled=include_disabled)
    if esfera:
        out = [s for s in out if s.esfera == esfera]
    if uf:
        out = [s for s in out if s.uf == uf]
    if tag:
        out = [s for s in out if tag in s.tags]
    return out


# ── Health check ────────────────────────────────────────────────────────


async def health_check(info: ScraperInfo, timeout: float = 10.0) -> dict[str, Any]:
    """Faz request GET na URL base para detectar se o portal está no ar."""
    started = datetime.now()
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "LicitaBrasil/2.0 health-check"},
        ) as client:
            resp = await client.get(info.base_url)
            elapsed = (datetime.now() - started).total_seconds()
            return {
                "name": info.name,
                "label": info.label,
                "status": "ok" if resp.status_code < 400 else "degraded",
                "http_code": resp.status_code,
                "elapsed_s": round(elapsed, 2),
                "timestamp": datetime.now().isoformat(),
            }
    except Exception as exc:
        elapsed = (datetime.now() - started).total_seconds()
        return {
            "name": info.name,
            "label": info.label,
            "status": "offline",
            "http_code": None,
            "elapsed_s": round(elapsed, 2),
            "error": str(exc),
            "timestamp": datetime.now().isoformat(),
        }


# ── DB stats ────────────────────────────────────────────────────────────


def db_stats(info: ScraperInfo) -> dict[str, Any]:
    """Retorna contagem total e última coleta do SQLite local, se existir."""
    path = info.db_path
    if not path.exists():
        return {"name": info.name, "exists": False, "total": 0}

    try:
        conn = sqlite3.connect(str(path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Total
        cur.execute(f"SELECT COUNT(*) AS c FROM {info.table_name}")
        total = cur.fetchone()["c"]

        # Última coleta (procura colunas comuns)
        last = None
        for col in ("data_coleta", "updated_at", "created_at"):
            try:
                cur.execute(
                    f"SELECT MAX({col}) AS m FROM {info.table_name}"
                )
                row = cur.fetchone()
                if row and row["m"]:
                    last = row["m"]
                    break
            except sqlite3.OperationalError:
                continue

        size_mb = round(path.stat().st_size / 1024 / 1024, 2)
        conn.close()
        return {
            "name": info.name,
            "exists": True,
            "total": total,
            "last_collected": last,
            "db_size_mb": size_mb,
            "db_path": str(path),
        }
    except Exception as exc:
        return {
            "name": info.name,
            "exists": True,
            "total": 0,
            "error": str(exc),
            "db_path": str(path),
        }


# ── Subprocess runner ───────────────────────────────────────────────────


def run_scraper(
    info: ScraperInfo,
    args: list[str] | None = None,
    timeout: int | None = None,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Executa o scraper como `python -m <module> [args]`.

    Args:
        info: scraper a executar.
        args: argumentos extras pro CLI nativo do scraper (ex: ['sync', '--max-pages', '5']).
        timeout: timeout em segundos (None = sem limite).
        capture_output: se True, captura stdout/stderr em strings.

    Returns:
        CompletedProcess. Em caso de erro, ``returncode != 0``.
    """
    cmd = [sys.executable, "-m", info.module]
    if args:
        cmd.extend(args)

    return subprocess.run(
        cmd,
        timeout=timeout,
        capture_output=capture_output,
        text=True,
        cwd=str(PROJECT_ROOT),
    )
