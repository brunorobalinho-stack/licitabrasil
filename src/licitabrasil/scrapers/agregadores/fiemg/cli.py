"""CLI Typer para o scraper FIEMG."""

from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from typing import Optional

import typer
from loguru import logger
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .client import FIEMGClient
from .config import Settings
from .parser import parse_detail, parse_feed, parse_listing
from .storage import Database


app = typer.Typer(
    name="fiemg",
    help="Scraper de Licitações FIEMG Compras",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(debug: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


@app.command()
def sync(
    max_pages: int = typer.Option(5, help="Limite de páginas (0 = todas)"),
    fetch_details: bool = typer.Option(True, "--details/--no-details"),
    use_feed: bool = typer.Option(True, "--feed/--no-feed"),
    debug: bool = typer.Option(False),
):
    """Sincroniza processos em andamento do portal FIEMG."""
    _setup_logging(debug)
    asyncio.run(_sync(max_pages, fetch_details, use_feed))


async def _sync(max_pages: int, fetch_details: bool, use_feed: bool):
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel.fit(
            f"[bold blue]FIEMG Compras Scraper[/bold blue]\n"
            f"DB: {settings.db_path}\n"
            f"Início: {datetime.now():%d/%m/%Y %H:%M}",
            border_style="blue",
        )
    )

    async with FIEMGClient(settings) as client:
        items = []
        if use_feed:
            xml = await client.fetch_feed()
            items = parse_feed(xml)
            if items:
                console.print(f"[green]✓[/green] Feed: {len(items)} itens")

        if not items:
            console.print("[dim]→ Parsing HTML...[/dim]")
            page = 1
            while True:
                html = await client.fetch_listing(page)
                page_items = parse_listing(html)
                if not page_items:
                    break
                items.extend(page_items)
                console.print(f"  Página {page}: {len(page_items)} itens")
                page += 1
                if max_pages and page > max_pages:
                    break

        if not items:
            console.print("[yellow]Nenhum item retornado.[/yellow]")
            return

        with Database(settings.db_path) as db:
            counts = {"new": 0, "updated": 0, "unchanged": 0, "errors": 0}
            for i, item in enumerate(items, 1):
                console.print(f"[dim]  [{i}/{len(items)}] {item.sde}[/dim]")
                try:
                    if fetch_details:
                        html = await client.fetch_detail(item.sde)
                        lic = parse_detail(html, item.sde)
                        lic.objeto_resumido = item.objeto_resumido or lic.objeto_resumido
                        lic.url_processo = item.url
                    else:
                        from .models import Licitacao
                        lic = Licitacao.from_sde(
                            item.sde,
                            objeto_resumido=item.objeto_resumido,
                            fase=item.fase,
                            data_encerramento_propostas=item.data_encerramento_propostas,
                            url_processo=item.url,
                        )

                    counts[db.upsert(lic)] += 1
                except Exception as exc:
                    logger.warning(f"Erro em {item.sde}: {exc}")
                    counts["errors"] += 1

            console.print(
                f"\n[bold]Resumo:[/bold] [green]{counts['new']} novos[/green] / "
                f"[yellow]{counts['updated']} atualizados[/yellow] / "
                f"{counts['unchanged']} inalterados / "
                f"[red]{counts['errors']} erros[/red]"
            )
            console.print(f"Total no banco: [bold]{db.count():,}[/bold]")


@app.command()
def probe(save: Optional[str] = typer.Option(None, help="Salvar HTML")):
    """Inspeciona a listagem inicial — útil pra validar seletores."""
    _setup_logging(True)

    async def _probe():
        settings = Settings()
        async with FIEMGClient(settings) as client:
            console.print(f"[dim]GET {settings.listing_url}[/dim]")
            html = await client.fetch_listing(page=1)
            console.print(f"[green]HTML:[/green] {len(html):,} bytes")
            items = parse_listing(html)
            console.print(f"[green]Itens parseados:[/green] {len(items)}")
            for it in items[:5]:
                console.print(f"  • {it.sde} | {it.fase} | {it.objeto_resumido[:60]}")
            if save:
                from pathlib import Path
                Path(save).write_text(html, encoding="utf-8")
                console.print(f"[blue]HTML salvo em {save}[/blue]")

    asyncio.run(_probe())


@app.command()
def open_now():
    """Lista processos com fase aberta para envio de propostas."""
    settings = Settings()
    if not settings.db_path.exists():
        console.print("[yellow]Banco vazio. Rode `sync` primeiro.[/yellow]")
        return

    with Database(settings.db_path) as db:
        rows = db.open_now()

    if not rows:
        console.print("[yellow]Nenhum processo aberto.[/yellow]")
        return

    table = Table(title=f"Processos abertos ({len(rows)})")
    table.add_column("SDE")
    table.add_column("Fase")
    table.add_column("Unidade")
    table.add_column("Objeto", overflow="fold")
    table.add_column("Prazo")
    for r in rows[:50]:
        table.add_row(
            r["sde"],
            r["fase"] or "—",
            r["unidade_compradora"] or "—",
            (r["objeto"] or "")[:80],
            r["data_encerramento_propostas"] or "—",
        )
    console.print(table)


@app.command()
def stats():
    settings = Settings()
    if not settings.db_path.exists():
        console.print("[yellow]Banco vazio. Rode `sync` primeiro.[/yellow]")
        return
    with Database(settings.db_path) as db:
        total = db.count()
    console.print(f"[bold]Total FIEMG:[/bold] {total:,} processos")
