"""CLI com Typer para o scraper da Central de Compras de Natal/RN."""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from .config import Settings, MODALIDADES
from .client import NatalClient
from .parser import parse_listing_page, parse_total_pages, parse_detail_page
from .storage import Storage
from .models import LicitacaoNatal

app = typer.Typer(
    name="central_compras_natal",
    help="Scraper de Licitacoes da Central de Compras de Natal/RN",
    no_args_is_help=True,
)
console = Console()


def setup_logging(debug: bool = False):
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


def _base_from_row(row: dict, settings: Settings) -> LicitacaoNatal:
    """Cria LicitacaoNatal base a partir de row do DB para enriquecimento."""
    return LicitacaoNatal(
        numero_licitacao=row["numero_licitacao"],
        modalidade_slug=row["modalidade_slug"],
        modalidade=row.get("modalidade", ""),
        record_id=row["record_id"],
        numero_processo=row.get("numero_processo", ""),
        tipo_licitacao=row.get("tipo_licitacao", ""),
        orgao=row.get("orgao", ""),
        objeto=row.get("objeto", ""),
        data_publicacao=row.get("data_publicacao"),
        url_detalhe=settings.detail_url(row["modalidade_slug"], row["record_id"]),
    )


# -- sync -----------------------------------------------------------------


@app.command()
def sync(
    modalidade: Optional[str] = typer.Option(None, help="Slug da modalidade (ex: pregao-eletronico). Omitir = todas"),
    max_pages: int = typer.Option(0, help="Limitar a N paginas por modalidade (0 = todas)"),
    with_detail: bool = typer.Option(False, help="Buscar detalhes apos listagem"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Sincroniza licitacoes da Central de Compras de Natal."""
    setup_logging(debug)
    asyncio.run(_sync(modalidade, max_pages, with_detail))


async def _sync(modalidade: Optional[str], max_pages: int, with_detail: bool):
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Storage(settings.db_path)

    mods = {modalidade: MODALIDADES[modalidade]} if modalidade else MODALIDADES

    try:
        async with NatalClient(settings) as client:
            console.print(f"\n[bold blue]>> Scraper Central de Compras Natal/RN — {datetime.now().strftime('%d/%m/%Y %H:%M')}[/bold blue]\n")

            total_new = 0
            total_updated = 0

            for slug, nome in mods.items():
                console.print(f"[cyan]> {nome}[/cyan] ({slug})")

                # Page 1 (GET or POST, first page works with POST too)
                html = await client.fetch_listing(slug, page=1)
                total_pages = parse_total_pages(html)

                if max_pages > 0:
                    total_pages = min(total_pages, max_pages)

                console.print(f"  [dim]{total_pages} paginas[/dim]")

                for page in range(1, total_pages + 1):
                    if page > 1:
                        html = await client.fetch_listing(slug, page=page)

                    items = parse_listing_page(html, slug, nome)
                    if not items:
                        logger.debug(f"  Page {page}: no items")
                        continue

                    inserted, updated = db.upsert_batch(items)
                    total_new += inserted
                    total_updated += updated

                    if page % 5 == 0 or page == total_pages:
                        console.print(f"  [dim]Pag {page}/{total_pages} — {len(items)} itens[/dim]")

                counts = db.count(slug)
                console.print(f"  [green]{counts['total']} registros[/green]")

            # Optional: enrich with detail pages
            if with_detail:
                await _enrich_all(client, db)

            total = db.count()
            console.print()
            console.print(Panel(
                f"[green]+ Novas:[/green] {total_new}  |  "
                f"[yellow]~ Atualizadas:[/yellow] {total_updated}  |  "
                f"[blue]# Total:[/blue] {total['total']}  |  "
                f"[cyan]Com detalhe:[/cyan] {total['com_detalhe']}",
                title="Natal/RN — Resultado",
                border_style="green",
            ))

    finally:
        db.close()


async def _enrich_all(client: NatalClient, db: Storage):
    """Enriquece registros sem detalhe."""
    pending = db.get_without_detail()
    if not pending:
        return

    console.print(f"\n[bold]Enriquecendo {len(pending)} registros...[/bold]")
    enriched = failed = 0

    for i, row in enumerate(pending):
        html = await client.fetch_detail(row["modalidade_slug"], row["record_id"])
        if html is None:
            failed += 1
            continue

        base = _base_from_row(row, client.settings)
        enriched_item = parse_detail_page(html, base)
        db.upsert(enriched_item)
        enriched += 1

        if (i + 1) % 50 == 0:
            console.print(f"  [dim]{i+1}/{len(pending)} ({enriched} ok, {failed} failed)[/dim]")

    console.print(f"  [green]Enriquecidos: {enriched}[/green], [red]Falhas: {failed}[/red]")


# -- enrich ---------------------------------------------------------------


@app.command()
def enrich(
    modalidade: Optional[str] = typer.Option(None, help="Slug da modalidade"),
    limit: int = typer.Option(100, help="Limite de registros"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Enriquece registros com dados da pagina de detalhe."""
    setup_logging(debug)
    asyncio.run(_enrich(modalidade, limit))


async def _enrich(modalidade: Optional[str], limit: int):
    settings = Settings()
    db = Storage(settings.db_path)

    try:
        pending = db.get_without_detail(modalidade or "")
        if not pending:
            console.print("[yellow]Nenhum registro para enriquecer.[/yellow]")
            return

        pending = pending[:limit]
        console.print(f"\n[bold blue]>> Enriquecendo {len(pending)} registros...[/bold blue]\n")

        enriched = failed = 0

        async with NatalClient(settings) as client:
            for i, row in enumerate(pending):
                html = await client.fetch_detail(row["modalidade_slug"], row["record_id"])
                if html is None:
                    failed += 1
                    continue

                base = LicitacaoNatal(
                    numero_licitacao=row["numero_licitacao"],
                    modalidade_slug=row["modalidade_slug"],
                    record_id=row["record_id"],
                    url_detalhe=client.settings.detail_url(row["modalidade_slug"], row["record_id"]),
                )
                enriched_item = parse_detail_page(html, base)
                db.upsert(enriched_item)
                enriched += 1

                if (i + 1) % 50 == 0:
                    console.print(f"  [dim]{i+1}/{len(pending)} ({enriched} ok, {failed} failed)[/dim]")

        console.print(Panel(
            f"[green]Enriquecidos:[/green] {enriched}  |  "
            f"[red]Falhas:[/red] {failed}",
            title="Enriquecimento Natal/RN",
            border_style="cyan",
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
        table.add_column("Licitacao", style="bold", width=14)
        table.add_column("Modalidade", width=18)
        table.add_column("Objeto", max_width=45)
        table.add_column("Orgao", style="green", width=25)
        table.add_column("Status", width=15)

        for r in results[:30]:
            obj = r["objeto"][:60] + "..." if len(r["objeto"]) > 60 else r["objeto"]
            table.add_row(
                r["numero_licitacao"],
                (r["modalidade"] or "")[:18],
                obj,
                (r["orgao"] or "")[:25],
                r.get("status", ""),
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

        console.print(f"\n[bold]Central de Compras Natal/RN — {total['total']} licitacoes ({total['com_detalhe']} com detalhe)[/bold]\n")

        by_mod = db.stats_by_modalidade()
        t_mod = Table(title="Por Modalidade", box=box.SIMPLE)
        t_mod.add_column("Modalidade", style="cyan")
        t_mod.add_column("Total", justify="right", style="green")
        t_mod.add_column("Com Detalhe", justify="right", style="blue")
        for row in by_mod:
            t_mod.add_row(row["modalidade"] or row["modalidade_slug"], str(row["total"]), str(row["com_detalhe"]))
        console.print(t_mod)

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
            path = Path(output) if output else settings.data_dir / "natal_export.csv"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        else:
            path = Path(output) if output else settings.data_dir / "natal_export.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)

        console.print(f"[green]Exportadas {len(data)} licitacoes para {path}[/green]")
    finally:
        db.close()
