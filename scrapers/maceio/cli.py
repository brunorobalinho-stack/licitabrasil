"""CLI com Typer para o scraper de Maceió."""

import asyncio
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

from .config import Settings
from .client import MaceioClient
from .storage import Database
from .downloader import DocumentDownloader

app = typer.Typer(
    name="maceio",
    help="Scraper de Licitações da Prefeitura de Maceió/AL",
    no_args_is_help=True,
)
console = Console()


def setup_logging(debug: bool = False):
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


# ── sync ──────────────────────────────────────────


@app.command()
def sync(
    mode: str = typer.Option("full", help="Modo: full, incremental, ids-only"),
    max_pages: int = typer.Option(0, help="Limitar a N páginas (0 = todas)"),
    max_ids: int = typer.Option(0, help="Limitar a N IDs para buscar via API (0 = todos)"),
    year: int = typer.Option(0, help="Filtrar por ano da modalidade"),
    status: Optional[str] = typer.Option(None, help="Filtrar por status"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Sincroniza licitações do portal de Maceió."""
    setup_logging(debug)
    asyncio.run(_sync(mode, max_pages, max_ids, year, status))


async def _sync(mode: str, max_pages: int, max_ids: int, year: int, status: Optional[str]):
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)

    try:
        async with MaceioClient(settings) as client:
            console.print(f"\n[bold blue]>> Scraper Maceió — {datetime.now().strftime('%d/%m/%Y %H:%M')}[/bold blue]\n")

            if mode == "ids-only":
                # Only discover IDs, don't fetch details
                ids = await client.fetch_listing_ids(max_pages=max_pages)
                known = db.get_known_ids()
                new_ids = [i for i in ids if i not in known]
                console.print(f"[green]Discovered {len(ids)} IDs total, {len(new_ids)} new[/green]")
                return

            # Step 1: Discover IDs from HTML listing
            console.print("[dim]Step 1: Discovering IDs from listing pages...[/dim]")
            all_ids = await client.fetch_listing_ids(max_pages=max_pages)

            if mode == "incremental":
                known = db.get_known_ids()
                target_ids = [i for i in all_ids if i not in known]
                console.print(f"[dim]Incremental: {len(target_ids)} new IDs (of {len(all_ids)} total)[/dim]")
            else:
                target_ids = all_ids

            if max_ids > 0:
                target_ids = target_ids[:max_ids]

            # Step 2: Fetch details via API
            console.print(f"[dim]Step 2: Fetching {len(target_ids)} licitações via API...[/dim]")
            new_count = 0
            updated_count = 0
            failed_count = 0

            for i, lid in enumerate(target_ids):
                lic = await client.fetch_licitacao_api(lid)
                if lic is None:
                    failed_count += 1
                    continue

                # Apply filters
                if year and lic.ano_modalidade != year:
                    continue
                if status and lic.status.lower() != status.lower():
                    continue

                is_new, is_updated = db.upsert_licitacao(lic)
                if is_new:
                    new_count += 1
                elif is_updated:
                    updated_count += 1

                if (i + 1) % 100 == 0:
                    console.print(f"  [dim]Progress: {i+1}/{len(target_ids)} ({new_count} new, {updated_count} updated)[/dim]")

            total = db.count()
            console.print()
            console.print(Panel(
                f"[green]+ Novas:[/green] {new_count}  |  "
                f"[yellow]~ Atualizadas:[/yellow] {updated_count}  |  "
                f"[red]x Falhas:[/red] {failed_count}  |  "
                f"[blue]# Total:[/blue] {total}",
                title="Maceio -- Resultado da Sincronizacao",
                border_style="green",
            ))

    finally:
        db.close()


# ── download-docs ─────────────────────────────────


@app.command("download-docs")
def download_docs(
    limit: int = typer.Option(0, help="Limitar a N documentos (0 = todos)"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Baixa documentos pendentes (editais, anexos, etc.)."""
    setup_logging(debug)
    asyncio.run(_download_docs(limit))


async def _download_docs(limit: int):
    settings = Settings()
    db = Database(settings.db_path)
    downloader = DocumentDownloader(settings, db)

    try:
        async with MaceioClient(settings) as client:
            console.print("\n[bold blue]>> Baixando documentos pendentes...[/bold blue]\n")
            downloaded, skipped, failed = await downloader.download_pending(client, limit=limit)

            console.print(Panel(
                f"[green]v Baixados:[/green] {downloaded}  |  "
                f"[yellow]= Dedup:[/yellow] {skipped}  |  "
                f"[red]x Falhas:[/red] {failed}",
                title="Download de Documentos",
                border_style="cyan",
            ))
    finally:
        db.close()


# ── search ────────────────────────────────────────


@app.command()
def search(
    keyword: str = typer.Argument(help="Palavra-chave para busca"),
):
    """Busca local no banco."""
    settings = Settings()
    db = Database(settings.db_path)

    try:
        results = db.search(keyword)
        if not results:
            console.print(f"[yellow]Nenhum resultado para '{keyword}'[/yellow]")
            return

        console.print(f"\n[bold]Encontradas {len(results)} licitações para '{keyword}':[/bold]\n")

        table = Table(box=box.ROUNDED, show_lines=True)
        table.add_column("ID", style="dim", width=6)
        table.add_column("Número", style="bold", width=12)
        table.add_column("Modalidade", width=15)
        table.add_column("Objeto", max_width=50)
        table.add_column("Órgão", style="green", width=20)
        table.add_column("Status", width=12)

        for r in results[:30]:
            numero = f"{r['numero_modalidade']}/{r['ano_modalidade']}" if r['numero_modalidade'] else r['num_processo']
            obj = r['objeto'][:80] + "..." if len(r['objeto']) > 80 else r['objeto']
            status_colors = {
                "Agendada": "[blue]Agendada[/blue]",
                "Em andamento": "[green]Em andamento[/green]",
                "Encerrada": "[dim]Encerrada[/dim]",
                "Cancelada": "[red]Cancelada[/red]",
                "Deserta": "[yellow]Deserta[/yellow]",
                "Suspensa": "[yellow]Suspensa[/yellow]",
                "Fracassada": "[red]Fracassada[/red]",
            }
            status_str = status_colors.get(r['status'], r['status'])
            table.add_row(str(r['id']), numero, r['modalidade'][:15], obj, r['orgao_nome'][:20], status_str)

        console.print(table)
    finally:
        db.close()


# ── stats ─────────────────────────────────────────


@app.command()
def stats():
    """Estatísticas da base."""
    settings = Settings()
    db = Database(settings.db_path)

    try:
        s = db.stats()
        if s["total"] == 0:
            console.print("[yellow]Banco vazio. Execute 'sync' primeiro.[/yellow]")
            return

        console.print(f"\n[bold]Maceió — {s['total']} licitações[/bold]\n")

        # By status
        t_status = Table(title="Por Status", box=box.SIMPLE)
        t_status.add_column("Status", style="cyan")
        t_status.add_column("Qtde", justify="right", style="green")
        for st, count in s["by_status"].items():
            t_status.add_row(st or "(vazio)", str(count))
        console.print(t_status)

        # By modalidade
        t_mod = Table(title="Por Modalidade", box=box.SIMPLE)
        t_mod.add_column("Modalidade", style="cyan")
        t_mod.add_column("Qtde", justify="right", style="green")
        for mod, count in s["by_modalidade"].items():
            t_mod.add_row(mod or "(vazio)", str(count))
        console.print(t_mod)

        # By ano
        t_ano = Table(title="Por Ano", box=box.SIMPLE)
        t_ano.add_column("Ano", style="cyan")
        t_ano.add_column("Qtde", justify="right", style="green")
        for ano, count in s["by_ano"].items():
            t_ano.add_row(str(ano), str(count))
        console.print(t_ano)

        # By orgao (top 10)
        t_org = Table(title="Top Órgãos", box=box.SIMPLE)
        t_org.add_column("Órgão", style="cyan")
        t_org.add_column("Qtde", justify="right", style="green")
        for org, count in list(s["by_orgao"].items())[:10]:
            t_org.add_row(org or "(vazio)", str(count))
        console.print(t_org)

        # Related data
        console.print(Panel(
            f"[cyan]Homologações:[/cyan] {s['homologacoes']}  |  "
            f"[cyan]Atas:[/cyan] {s['atas']}  |  "
            f"[cyan]Documentos:[/cyan] {s['documentos']}  |  "
            f"[green]Valor total contratado:[/green] R$ {s['valor_total_contratado']:,.2f}",
            title="Dados Relacionados",
            border_style="dim",
        ))

    finally:
        db.close()


# ── export ────────────────────────────────────────


@app.command()
def export(
    format: str = typer.Option("json", help="Formato: json, csv"),
    output: Optional[str] = typer.Option(None, help="Arquivo de saída"),
):
    """Exportar dados."""
    settings = Settings()
    db = Database(settings.db_path)

    try:
        if format == "csv":
            path = Path(output) if output else settings.data_dir / "maceio_export.csv"
            count = db.export_csv(path)
        else:
            path = Path(output) if output else settings.data_dir / "maceio_export.json"
            count = db.export_json(path)

        console.print(f"[green]Exportadas {count} licitações para {path}[/green]")
    finally:
        db.close()
