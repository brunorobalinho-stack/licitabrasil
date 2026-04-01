"""CLI com Typer para o scraper da Prefeitura de SP."""

import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .config import Settings, MODALIDADES
from .client import PrefeituraSPClient
from .models import parse_api_item
from .storage import Storage

app = typer.Typer(
    name="prefeitura_sp",
    help="Scraper de licitacoes da Prefeitura de SP (via PNCP)",
    no_args_is_help=True,
)
console = Console()


def setup_logging(debug: bool = False):
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


# -- sync -----------------------------------------------------------------


@app.command()
def sync(
    days: int = typer.Option(7, help="Janela de dias para buscar (padrao: 7)"),
    full: bool = typer.Option(False, help="Buscar 365 dias (max da API)"),
    modalidade: Optional[int] = typer.Option(None, help="Codigo da modalidade (1-13). Omitir = todas"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Sincroniza licitacoes da Prefeitura de SP via PNCP."""
    setup_logging(debug)
    if full:
        days = 365
    asyncio.run(_sync(days, modalidade))


async def _sync(days: int, modalidade: Optional[int]):
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Storage(settings.db_path)

    data_final = datetime.now()
    data_inicial = data_final - timedelta(days=days)
    dt_ini = data_inicial.strftime("%Y%m%d")
    dt_fim = data_final.strftime("%Y%m%d")

    mods = {modalidade: MODALIDADES[modalidade]} if modalidade else MODALIDADES

    try:
        async with PrefeituraSPClient(settings) as client:
            console.print(
                f"\n[bold blue]>> Scraper Prefeitura de SP (PNCP) -- "
                f"{datetime.now().strftime('%d/%m/%Y %H:%M')}[/bold blue]"
            )
            console.print(
                f"[dim]Periodo: {data_inicial.strftime('%d/%m/%Y')} a "
                f"{data_final.strftime('%d/%m/%Y')} ({days} dias)[/dim]\n"
            )

            total_new = 0
            total_updated = 0
            total_items = 0
            total_filtered = 0

            for mod_id, mod_nome in mods.items():
                result = await client.fetch_page(dt_ini, dt_fim, mod_id, pagina=1)
                if not result or result.get("empty", True):
                    continue

                total_pages = result.get("totalPaginas", 1)
                total_registros = result.get("totalRegistros", 0)
                console.print(f"[cyan]> {mod_nome}[/cyan] ({total_registros} registros, {total_pages} pags)")

                page = 1
                while True:
                    if page > 1:
                        result = await client.fetch_page(dt_ini, dt_fim, mod_id, pagina=page)
                        if not result or result.get("empty", True):
                            break

                    items_raw = result.get("data", [])
                    if not items_raw:
                        break

                    # Parse e filtrar esfera Municipal
                    items = []
                    for raw in items_raw:
                        parsed = parse_api_item(raw)
                        if parsed:
                            items.append(parsed)

                    total_items += len(items_raw)
                    total_filtered += len(items_raw) - len(items)

                    if items:
                        inserted, updated = db.upsert_batch(items)
                        total_new += inserted
                        total_updated += updated

                    if page % 5 == 0 or page == total_pages:
                        console.print(
                            f"  [dim]Pag {page}/{total_pages} -- "
                            f"{len(items)} municipais de {len(items_raw)} total[/dim]"
                        )

                    if page >= total_pages:
                        break
                    page += 1

            counts = db.count()
            console.print()
            console.print(Panel(
                f"[green]+ Novas:[/green] {total_new}  |  "
                f"[yellow]~ Atualizadas:[/yellow] {total_updated}  |  "
                f"[blue]# Total DB:[/blue] {counts['total']}  |  "
                f"[dim]Filtrados (nao-municipal):[/dim] {total_filtered}",
                title="Prefeitura SP -- Resultado",
                border_style="green",
            ))

    finally:
        db.close()


# -- search ---------------------------------------------------------------


@app.command()
def search(
    keyword: str = typer.Argument(help="Palavra-chave para busca"),
):
    """Busca local no banco."""
    settings = Settings()
    db = Storage(settings.db_path)

    try:
        results = db.search(keyword)
        if not results:
            console.print(f"[yellow]Nenhum resultado para '{keyword}'[/yellow]")
            return

        console.print(f"\n[bold]Encontradas {len(results)} licitacoes para '{keyword}':[/bold]\n")

        table = Table(box=box.ROUNDED, show_lines=True)
        table.add_column("Modalidade", width=16)
        table.add_column("Orgao", style="green", width=30)
        table.add_column("Objeto", max_width=40)
        table.add_column("Valor Est.", justify="right", width=14)
        table.add_column("Situacao", width=15)

        for r in results[:30]:
            obj = r["objeto"][:55] + "..." if len(r["objeto"]) > 55 else r["objeto"]
            valor = f"R$ {r['valor_estimado']:,.2f}" if r.get("valor_estimado") else "-"
            table.add_row(
                (r["modalidade"] or "")[:16],
                (r["orgao_nome"] or "")[:30],
                obj,
                valor,
                r.get("situacao", ""),
            )

        console.print(table)
    finally:
        db.close()


# -- stats ----------------------------------------------------------------


@app.command()
def stats():
    """Estatisticas da base."""
    settings = Settings()
    db = Storage(settings.db_path)

    try:
        total = db.count()
        if total["total"] == 0:
            console.print("[yellow]Banco vazio. Execute 'sync' primeiro.[/yellow]")
            return

        console.print(f"\n[bold]Prefeitura de SP (PNCP) -- {total['total']} licitacoes[/bold]\n")

        # Por modalidade
        by_mod = db.stats_by_modalidade()
        t_mod = Table(title="Por Modalidade", box=box.SIMPLE)
        t_mod.add_column("Modalidade", style="cyan")
        t_mod.add_column("Total", justify="right", style="green")
        t_mod.add_column("Valor Total Est.", justify="right")
        for row in by_mod:
            valor = f"R$ {row['valor_total']:,.2f}" if row.get("valor_total") else "-"
            t_mod.add_row(row["modalidade"] or str(row["modalidade_id"]), str(row["total"]), valor)
        console.print(t_mod)

        # Por orgao
        by_orgao = db.stats_by_orgao()
        t_org = Table(title="Por Orgao", box=box.SIMPLE)
        t_org.add_column("Orgao", style="cyan", max_width=50)
        t_org.add_column("Total", justify="right", style="green")
        for row in by_orgao[:15]:
            t_org.add_row(row["orgao_nome"][:50], str(row["total"]))
        console.print(t_org)

        # Por situacao
        by_sit = db.stats_by_situacao()
        t_sit = Table(title="Por Situacao", box=box.SIMPLE)
        t_sit.add_column("Situacao", style="cyan")
        t_sit.add_column("Total", justify="right", style="green")
        for row in by_sit:
            t_sit.add_row(row["situacao"], str(row["total"]))
        console.print(t_sit)

    finally:
        db.close()


# -- export ---------------------------------------------------------------


@app.command()
def export(
    format: str = typer.Option("json", help="Formato: json, csv"),
    output: Optional[str] = typer.Option(None, help="Arquivo de saida"),
):
    """Exportar dados."""
    settings = Settings()
    db = Storage(settings.db_path)

    try:
        data = db.export_all()
        if not data:
            console.print("[yellow]Banco vazio.[/yellow]")
            return

        if format == "csv":
            import csv
            path = Path(output) if output else settings.data_dir / "prefeitura_sp_export.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        else:
            path = Path(output) if output else settings.data_dir / "prefeitura_sp_export.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        console.print(f"[green]Exportadas {len(data)} licitacoes para {path}[/green]")
    finally:
        db.close()
