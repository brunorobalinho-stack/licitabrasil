"""CLI Typer para o scraper PE-Integrado."""

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

from .client import PEIntegradoClient
from .config import Settings
from .parser import parse_detail, parse_feed, parse_listing
from .storage import Database


app = typer.Typer(
    name="peintegrado",
    help="Scraper do Portal de Compras de Pernambuco (PE-Integrado)",
    no_args_is_help=True,
)
console = Console()


def _setup_logging(debug: bool = False) -> None:
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


# ── sync ──────────────────────────────────────────────────────────────


@app.command()
def sync(
    max_pages: int = typer.Option(5, help="Limitar a N páginas de listagem (0 = todas)"),
    fetch_details: bool = typer.Option(
        True, "--details/--no-details", help="Buscar detalhes de cada processo"
    ),
    use_feed: bool = typer.Option(True, "--feed/--no-feed", help="Tentar RSS antes do HTML"),
    engine: str = typer.Option(
        "httpx",
        "--engine",
        help="'httpx' (rápido, mas não renderiza JS) ou 'playwright' (renderiza tudo)",
    ),
    kind: str = typer.Option(
        "andamento",
        "--kind",
        help="andamento|dispensa|encerradas (válido apenas com --engine playwright)",
    ),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Sincroniza licitações do PE-Integrado para o SQLite local."""
    _setup_logging(debug)
    if engine == "playwright":
        asyncio.run(_sync_playwright(max_pages, fetch_details, kind))
    else:
        asyncio.run(_sync(max_pages, fetch_details, use_feed))


async def _sync_playwright(max_pages: int, fetch_details: bool, kind: str) -> None:
    """Sync usando Playwright — renderiza JS e captura tabela populada."""
    from .client_playwright import PEIntegradoPlaywrightClient
    from .models import Licitacao

    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel.fit(
            f"[bold magenta]PE-Integrado Scraper (Playwright)[/bold magenta]\n"
            f"Kind: {kind}\n"
            f"DB: {settings.db_path}\n"
            f"Início: {datetime.now():%d/%m/%Y %H:%M}",
            border_style="magenta",
        )
    )

    async with PEIntegradoPlaywrightClient(settings) as client:
        htmls = await client.fetch_listing(kind=kind, max_pages=max_pages or 1)
        console.print(f"[green]✓[/green] {len(htmls)} página(s) capturada(s)")

        all_items = []
        for i, html in enumerate(htmls, 1):
            items = parse_listing(html)
            console.print(f"  Página {i}: {len(items)} itens")
            all_items.extend(items)

        if not all_items:
            console.print("[yellow]Nenhum item retornado.[/yellow]")
            return

        with Database(settings.db_path) as db:
            counts = {"new": 0, "updated": 0, "unchanged": 0, "errors": 0}
            for it in all_items:
                try:
                    if fetch_details:
                        html = await client.fetch_detail(it.numero)
                        lic = parse_detail(html, it.numero)
                        lic.objeto_resumido = it.objeto_resumido or lic.objeto_resumido
                        lic.url_processo = it.url
                    else:
                        lic = Licitacao.from_numero(
                            it.numero,
                            objeto_resumido=it.objeto_resumido,
                            situacao=it.situacao,
                            url_processo=it.url,
                        )
                    counts[db.upsert(lic)] += 1
                except Exception as exc:
                    logger.warning(f"Erro em {it.numero}: {exc}")
                    counts["errors"] += 1

            console.print(
                f"\n[bold]Resumo:[/bold] [green]{counts['new']} novos[/green] / "
                f"[yellow]{counts['updated']} atualizados[/yellow] / "
                f"{counts['unchanged']} inalterados / "
                f"[red]{counts['errors']} erros[/red]"
            )
            console.print(f"Total no banco: [bold]{db.count():,}[/bold]")


async def _sync(max_pages: int, fetch_details: bool, use_feed: bool) -> None:
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    console.print(
        Panel.fit(
            f"[bold blue]PE-Integrado Scraper[/bold blue]\n"
            f"DB: {settings.db_path}\n"
            f"Início: {datetime.now():%d/%m/%Y %H:%M}",
            border_style="blue",
        )
    )

    async with PEIntegradoClient(settings) as client:
        # 1) Tenta RSS primeiro
        items = []
        if use_feed:
            console.print("[dim]→ Tentando feed RSS...[/dim]")
            xml = await client.fetch_feed()
            items = parse_feed(xml)
            if items:
                console.print(f"[green]✓[/green] Feed retornou {len(items)} itens")

        # 2) Fallback / complemento: HTML
        if not items:
            console.print("[dim]→ Parsing HTML de listagem...[/dim]")
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
            console.print("[yellow]Nenhum processo retornado.[/yellow]")
            return

        # 3) Buscar detalhes e gravar
        with Database(settings.db_path) as db:
            counts = {"new": 0, "updated": 0, "unchanged": 0, "errors": 0}

            for i, item in enumerate(items, 1):
                console.print(f"[dim]  [{i}/{len(items)}] {item.numero}[/dim]")
                try:
                    if fetch_details:
                        html = await client.fetch_detail(item.numero)
                        lic = parse_detail(html, item.numero)
                        lic.objeto_resumido = item.objeto_resumido or lic.objeto_resumido
                        lic.url_processo = item.url
                    else:
                        from .models import Licitacao
                        lic = Licitacao.from_numero(
                            item.numero,
                            objeto_resumido=item.objeto_resumido,
                            situacao=item.situacao,
                            url_processo=item.url,
                        )

                    counts[db.upsert(lic)] += 1
                except Exception as exc:
                    logger.warning(f"Erro em {item.numero}: {exc}")
                    counts["errors"] += 1

            console.print(
                f"\n[bold]Resumo:[/bold] [green]{counts['new']} novos[/green] / "
                f"[yellow]{counts['updated']} atualizados[/yellow] / "
                f"{counts['unchanged']} inalterados / "
                f"[red]{counts['errors']} erros[/red]"
            )
            console.print(f"Total no banco: [bold]{db.count():,}[/bold]")


# ── probe ─────────────────────────────────────────────────────────────


@app.command()
def probe(
    save: Optional[str] = typer.Option(None, help="Salvar HTML em arquivo para inspeção"),
):
    """Baixa a página inicial de listagem e imprime estatísticas — útil
    para validar seletores antes de rodar ``sync``.
    """
    _setup_logging(True)

    async def _probe():
        settings = Settings()
        async with PEIntegradoClient(settings) as client:
            console.print(f"[dim]GET {settings.listing_url}[/dim]")
            html = await client.fetch_listing(page=1)

            console.print(f"[green]HTML recebido:[/green] {len(html):,} bytes")
            console.print(f"[green]Tem ViewState:[/green] {bool(client._view_state)}")

            items = parse_listing(html)
            console.print(f"[green]Itens parseados:[/green] {len(items)}")
            for it in items[:5]:
                console.print(f"  • {it.numero} | {it.modalidade} | {it.objeto_resumido[:60]}")

            if save:
                from pathlib import Path
                Path(save).write_text(html, encoding="utf-8")
                console.print(f"[blue]HTML salvo em {save}[/blue]")

    asyncio.run(_probe())


# ── stats ─────────────────────────────────────────────────────────────


@app.command()
def stats():
    """Mostra estatísticas do SQLite local."""
    settings = Settings()
    if not settings.db_path.exists():
        console.print("[yellow]Banco ainda não existe. Rode `sync` primeiro.[/yellow]")
        return

    with Database(settings.db_path) as db:
        total = db.count()
        latest = db.latest(limit=10)

    console.print(f"[bold]Total:[/bold] {total:,} licitações")
    table = Table(title="Últimas coletas")
    table.add_column("Número")
    table.add_column("Modalidade")
    table.add_column("Órgão")
    table.add_column("Objeto", overflow="fold")
    table.add_column("Situação")
    for r in latest:
        table.add_row(
            r["numero"],
            r["modalidade"] or "—",
            r["orgao_sigla"] or "—",
            (r["objeto"] or "")[:80],
            r["situacao"] or "—",
        )
    console.print(table)


# ── search ────────────────────────────────────────────────────────────


@app.command()
def search(
    keyword: str = typer.Argument(help="Palavra-chave (busca em objeto/órgão/número)"),
):
    """Busca local por palavra-chave no SQLite."""
    settings = Settings()
    with Database(settings.db_path) as db:
        rows = db.search(keyword)

    if not rows:
        console.print(f"[yellow]Nenhum resultado para '{keyword}'.[/yellow]")
        return

    table = Table(title=f"Resultados para '{keyword}' ({len(rows)})")
    table.add_column("Número")
    table.add_column("Modalidade")
    table.add_column("Órgão")
    table.add_column("Objeto", overflow="fold")
    for r in rows[:50]:
        table.add_row(
            r["numero"],
            r["modalidade"] or "—",
            r["orgao_sigla"] or "—",
            (r["objeto"] or "")[:100],
        )
    console.print(table)
