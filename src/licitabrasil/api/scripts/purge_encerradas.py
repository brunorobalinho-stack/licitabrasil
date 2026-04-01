"""Purge de licitacoes encerradas do banco PostgreSQL.

Uso:
    python -m app.scripts.purge_encerradas                          # dry-run
    python -m app.scripts.purge_encerradas --export-csv --confirm   # export + delete
    python -m app.scripts.purge_encerradas --confirm                # delete (prompt)
    python -m app.scripts.purge_encerradas --dias 60                # threshold 60 dias
"""

import argparse
import asyncio
import csv
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("purge")

PURGE_DIR = Path("data/purged")
MAX_CSV_FILES = 12

# ── Patterns de status ────────────────────────────────
# Usados tanto no SQL (ILIKE) quanto no Python (in)

PURGE_PATTERNS = [
    "encerrad",     # Encerrada, Encerrado
    "homolog",      # Homologacao, homologada, Adjudicacao/Homologacao
    "adjudic",      # Adjudicacao
    "desert",       # Deserta, Deserto
    "fracassad",    # Fracassada, Fracassado
    "revog",        # Revogada, Revogacao
    "anul",         # Anulada, Anulacao
    "cancelad",     # Cancelada, Cancelado
    "conclu",       # Concluida, Concluido
    "finaliz",      # Finalizada, Finalizado
    "exclu",        # Excluida (removida na fonte)
]

SUSPEND_PATTERNS = [
    "suspens",      # Suspensa, Suspenso (regra dos 90 dias)
]

EXPORT_COLUMNS = [
    "id", "numero_processo", "modalidade", "objeto", "orgao", "uf",
    "status", "data_publicacao", "data_abertura", "data_encerramento",
    "valor_estimado", "fonte", "fonte_id", "url_origem", "data_coleta",
]


# ── Logica de classificacao (testavel sem banco) ──────


def classify_status(status: str | None) -> str:
    """Classifica um status como 'purge', 'suspend' ou 'keep'.

    Suspend e checado primeiro porque tem regra especial (90 dias).
    """
    if not status:
        return "keep"
    s = status.lower()
    for p in SUSPEND_PATTERNS:
        if p in s:
            return "suspend"
    for p in PURGE_PATTERNS:
        if p in s:
            return "purge"
    return "keep"


def should_purge(
    status: str | None,
    data_publicacao: datetime | None,
    data_abertura: datetime | None,
    dias_protecao: int = 30,
    now: datetime | None = None,
) -> bool:
    """Determina se uma licitacao deve ser purgada.

    Regras:
    - Status 'keep' -> nunca purga
    - Protecao temporal: nao purga se data_publicacao < dias_protecao dias
    - Suspensa: so purga se data_abertura > 90 dias atras E definida
    """
    now = now or datetime.now()
    cls = classify_status(status)

    if cls == "keep":
        return False

    if data_publicacao and (now - data_publicacao).days <= dias_protecao:
        return False

    if cls == "suspend":
        if not data_abertura:
            return False
        if (now - data_abertura).days < 90:
            return False

    return True


# ── SQL ───────────────────────────────────────────────


def _build_where() -> str:
    """Monta clausula WHERE para licitacoes purgaveis.

    Patterns sao constantes hardcoded (nao interpoladas de user input).
    O parametro de dias e passado como bind parameter ':dias' via
    ``text(...).bindparams(dias=N)`` em cada chamada.
    """
    immediate = " OR ".join(f"l.status ILIKE '%{p}%'" for p in PURGE_PATTERNS)
    suspended = " OR ".join(f"l.status ILIKE '%{p}%'" for p in SUSPEND_PATTERNS)

    return (
        f"(({immediate}) AND NOT ({suspended})"
        f" OR ({suspended}) AND l.data_abertura IS NOT NULL"
        f" AND l.data_abertura < NOW() - INTERVAL '90 days')"
        f" AND (l.data_publicacao IS NULL"
        f" OR l.data_publicacao < NOW() - :dias * INTERVAL '1 day')"
    )


async def get_stats(session, dias: int) -> dict:
    where = _build_where()
    bp = {"dias": dias}

    result = await session.execute(
        text(
            f"SELECT COALESCE(NULLIF(l.status, ''), '(vazio)'), COUNT(*)"
            f" FROM licitacoes l WHERE {where}"
            f" GROUP BY l.status ORDER BY COUNT(*) DESC"
        ).bindparams(**bp)
    )
    status_counts = [(r[0] or "(NULL)", r[1]) for r in result]

    result = await session.execute(
        text(
            f"SELECT COUNT(*) FROM documentos d"
            f" WHERE d.licitacao_id IN (SELECT l.id FROM licitacoes l WHERE {where})"
        ).bindparams(**bp)
    )
    total_docs = result.scalar()

    result = await session.execute(
        text(
            f"SELECT MIN(l.data_publicacao), MAX(l.data_publicacao)"
            f" FROM licitacoes l WHERE {where}"
        ).bindparams(**bp)
    )
    row = result.one()
    date_min, date_max = row[0], row[1]

    # Protegidas pela janela temporal
    immediate = " OR ".join(f"l.status ILIKE '%{p}%'" for p in PURGE_PATTERNS)
    suspended = " OR ".join(f"l.status ILIKE '%{p}%'" for p in SUSPEND_PATTERNS)
    result = await session.execute(
        text(
            f"SELECT COUNT(*) FROM licitacoes l"
            f" WHERE (({immediate}) OR ({suspended}))"
            f" AND l.data_publicacao IS NOT NULL"
            f" AND l.data_publicacao >= NOW() - :dias * INTERVAL '1 day'"
        ).bindparams(**bp)
    )
    protected = result.scalar()

    result = await session.execute(text(
        f"SELECT COUNT(*) FROM licitacoes l"
        f" WHERE ({suspended})"
        f" AND (l.data_abertura IS NULL OR l.data_abertura >= NOW() - INTERVAL '90 days')"
    ))
    suspend_kept = result.scalar()

    total = sum(c for _, c in status_counts)
    return {
        "status_counts": status_counts,
        "total": total,
        "total_docs": total_docs,
        "date_min": date_min,
        "date_max": date_max,
        "protected": protected,
        "suspend_kept": suspend_kept,
    }


async def do_export_csv(session, dias: int) -> Path:
    PURGE_DIR.mkdir(parents=True, exist_ok=True)

    where = _build_where()
    bp = {"dias": dias}
    ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    path = PURGE_DIR / f"purge_{ts}.csv"

    cols = ", ".join(f"l.{c}" for c in EXPORT_COLUMNS)
    result = await session.execute(
        text(f"SELECT {cols} FROM licitacoes l WHERE {where}").bindparams(**bp)
    )
    rows = result.fetchall()

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(EXPORT_COLUMNS)
        for row in rows:
            writer.writerow(row)

    log.info("Exportados %s registros para %s", f"{len(rows):,}", path)

    # Manter apenas ultimos MAX_CSV_FILES
    csvs = sorted(PURGE_DIR.glob("purge_*.csv"), key=lambda p: p.stat().st_mtime)
    while len(csvs) > MAX_CSV_FILES:
        old = csvs.pop(0)
        old.unlink()
        log.info("CSV antigo removido: %s", old.name)

    return path


async def execute_purge(session, dias: int) -> int:
    where = _build_where()
    bp = {"dias": dias}
    result = await session.execute(
        text(
            f"DELETE FROM licitacoes"
            f" WHERE id IN (SELECT l.id FROM licitacoes l WHERE {where})"
        ).bindparams(**bp)
    )
    deleted = result.rowcount
    await session.commit()
    log.info("Excluidas %s licitacoes (documentos cascateados pelo banco)", f"{deleted:,}")
    return deleted


# ── Output ────────────────────────────────────────────


def print_report(stats: dict, dias: int, confirm: bool):
    mode = "PURGE" if confirm else "PURGE DRY-RUN"
    print(f"\n{'='*50}")
    print(f"  {mode} -- LicitaBrasil")
    print(f"{'='*50}\n")

    print("  Licitacoes que seriam excluidas:")
    for status, cnt in stats["status_counts"]:
        label = (status or "(NULL)")[:30]
        dots = "." * max(1, 32 - len(label))
        print(f"    {label} {dots} {cnt:>8,}")
    print(f"    {'_'*42}")
    print(f"    {'TOTAL'} {'.' * 27} {stats['total']:>8,}")
    print()

    print("  Registros relacionados:")
    print(f"    documentos ........ {stats['total_docs']:,}")
    print()

    if stats["date_min"] and stats["date_max"]:
        d1 = stats["date_min"].strftime("%Y-%m-%d")
        d2 = stats["date_max"].strftime("%Y-%m-%d")
        print(f"  Range de datas: {d1} -> {d2}")
    print(f"  Protegidas (< {dias} dias): {stats['protected']} licitacoes mantidas")
    if stats["suspend_kept"]:
        print(f"  Suspensas mantidas (< 90 dias): {stats['suspend_kept']}")
    print()


# ── Main ──────────────────────────────────────────────


async def run(dias: int, confirm: bool, export: bool):
    engine = create_async_engine(settings.database_url)
    sm = async_sessionmaker(engine, expire_on_commit=False)

    async with sm() as session:
        stats = await get_stats(session, dias)
        print_report(stats, dias, confirm)

        if stats["total"] == 0:
            print("  Nenhuma licitacao a purgar.\n")
            await engine.dispose()
            return

        if not confirm:
            print("  Para executar:")
            print("    python -m app.scripts.purge_encerradas --confirm")
            print("  Recomendado:")
            print("    python -m app.scripts.purge_encerradas --export-csv --confirm\n")
            await engine.dispose()
            return

        if not export:
            try:
                resp = input(
                    "  Recomendo rodar com --export-csv primeiro para ter backup.\n"
                    "  Continuar mesmo assim? [s/N] "
                )
            except EOFError:
                resp = "n"
            if resp.strip().lower() != "s":
                print("  Abortado.\n")
                await engine.dispose()
                return

        if export:
            csv_path = await do_export_csv(session, dias)
            print(f"  Backup salvo em: {csv_path}\n")

        deleted = await execute_purge(session, dias)
        print(f"\n  {deleted:,} licitacoes excluidas com sucesso.\n")

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(
        description="Purge de licitacoes encerradas do LicitaBrasil"
    )
    parser.add_argument(
        "--confirm", action="store_true",
        help="Executar exclusao de fato (sem isso, apenas dry-run)",
    )
    parser.add_argument(
        "--export-csv", action="store_true",
        help="Exportar CSV backup antes de excluir",
    )
    parser.add_argument(
        "--dias", type=int, default=30,
        help="Dias de protecao temporal para data_publicacao (padrao: 30)",
    )
    args = parser.parse_args()
    asyncio.run(run(args.dias, args.confirm, args.export_csv))


if __name__ == "__main__":
    main()
