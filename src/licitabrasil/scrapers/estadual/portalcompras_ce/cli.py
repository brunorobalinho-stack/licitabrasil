"""CLI com Typer para o scraper do Portal de Compras CE."""

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
from .client import LicitawebClient
from .parser import parse_listing_page, parse_total_records, parse_total_pages, parse_detail_page
from .storage import Database

app = typer.Typer(
    name="portalcompras_ce",
    help="Scraper de Licitacoes do Portal de Compras do Ceara (Licitaweb/S2GPR)",
    no_args_is_help=True,
)
console = Console()


def setup_logging(debug: bool = False):
    logger.remove()
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")


# -- sync (listing) ---------------------------------------------------


@app.command()
def sync(
    max_pages: int = typer.Option(0, help="Limitar a N paginas (0 = todas)"),
    resume: bool = typer.Option(True, help="Retomar de onde parou"),
    reset: bool = typer.Option(False, help="Resetar progresso e comecar do zero"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Sincroniza licitacoes via listagem paginada do Licitaweb."""
    setup_logging(debug)
    asyncio.run(_sync(max_pages, resume, reset))


async def _sync(max_pages: int, resume: bool, reset: bool):
    settings = Settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    db = Database(settings.db_path)

    try:
        if reset:
            db.reset_progress()
            console.print("[yellow]Progresso resetado.[/yellow]")

        async with LicitawebClient(settings) as client:
            console.print(f"\n[bold blue]>> Scraper Portal Compras CE -- {datetime.now().strftime('%d/%m/%Y %H:%M')}[/bold blue]\n")

            # Step 1: Init JSF session and get page 1
            console.print("[dim]Inicializando sessao JSF...[/dim]")
            first_html = await client.init_listing_session()

            total_records = parse_total_records(first_html)
            total_pages = parse_total_pages(first_html)
            console.print(f"[green]Total: {total_records:,} registros em {total_pages:,} paginas[/green]")

            if max_pages > 0:
                total_pages = min(total_pages, max_pages)

            # Check progress
            progress = db.get_progress()
            start_page = 1
            if resume and progress["last_page"] > 0 and not reset:
                start_page = progress["last_page"] + 1
                console.print(f"[yellow]Retomando da pagina {start_page} (checkpoint anterior)[/yellow]")

            db.save_progress(start_page - 1, total_pages, total_records)

            # Step 2: Parse page 1 if starting from beginning
            new_count = 0
            updated_count = 0
            failed_pages = 0

            if start_page == 1:
                records = parse_listing_page(first_html)
                for lic in records:
                    is_new, is_updated = db.upsert(lic)
                    if is_new:
                        new_count += 1
                    elif is_updated:
                        updated_count += 1
                db.save_progress(1, total_pages, total_records)
                start_page = 2

            # Step 3: Paginate remaining pages
            session_reset_interval = 500  # re-init session every N pages
            # Guards anti-stuck (Bug Dia 0.5 #4):
            # - consecutive_failures: exceptions seguidas. Resetado em
            #   pagina ok. Threshold 10 aborta a corrida pra preservar
            #   checkpoint no ultimo page real.
            # - consecutive_empty: paginas que vieram vazias mesmo apos
            #   reinit. Antes este caso CAIA pra db.save_progress(page)
            #   incondicional -- checkpoint avancava com zero registros,
            #   simulando progresso falso (sintoma "stuck").
            consecutive_failures = 0
            consecutive_empty = 0
            EMPTY_ABORT_THRESHOLD = 3
            FAILURE_ABORT_THRESHOLD = 10

            for page in range(start_page, total_pages + 1):
                try:
                    # Re-init session periodically to avoid expiration
                    if (page - start_page) > 0 and (page - start_page) % session_reset_interval == 0:
                        await client.reinit_session()
                        # Navigate to the correct page after re-init
                        # The datascroller supports jumping to any page number

                    html = await client.fetch_listing_page(page)
                    records = parse_listing_page(html)

                    if not records:
                        # Session might have expired
                        logger.warning(f"Page {page}: empty results, re-initializing session...")
                        await client.reinit_session()
                        html = await client.fetch_listing_page(page)
                        records = parse_listing_page(html)

                    if not records:
                        # Vazio mesmo apos retry: causas possiveis sao
                        # session expirada que reinit nao recuperou,
                        # parser quebrado (HTML mudou), ou portal com
                        # problema. NAO avanca checkpoint -- preserva o
                        # last_page no ultimo page com dados.
                        consecutive_empty += 1
                        failed_pages += 1
                        logger.error(
                            f"Page {page}: vazia mesmo apos reinit "
                            f"(consecutive_empty={consecutive_empty})"
                        )
                        if consecutive_empty >= EMPTY_ABORT_THRESHOLD:
                            console.print(
                                f"[red]Abortando: {EMPTY_ABORT_THRESHOLD} paginas "
                                "vazias consecutivas. Portal pode estar com problema "
                                "ou o parser quebrou. Checkpoint preservado no ultimo "
                                "page com dados -- rode 'sync --resume' depois.[/red]"
                            )
                            break
                        continue

                    # Sucesso real: reseta os contadores anti-stuck.
                    consecutive_empty = 0
                    consecutive_failures = 0

                    for lic in records:
                        is_new, is_updated = db.upsert(lic)
                        if is_new:
                            new_count += 1
                        elif is_updated:
                            updated_count += 1

                    db.save_progress(page)

                    if page % 100 == 0:
                        total = db.count()
                        elapsed_pct = ((page - start_page + 1) / (total_pages - start_page + 1)) * 100
                        console.print(
                            f"  [dim]Pagina {page}/{total_pages} ({elapsed_pct:.1f}%) | "
                            f"{new_count} novas, {updated_count} atualizadas | "
                            f"Total DB: {total:,}[/dim]"
                        )

                except Exception as e:
                    consecutive_failures += 1
                    failed_pages += 1
                    logger.warning(
                        f"Page {page} failed: {e} "
                        f"(consecutive_failures={consecutive_failures})"
                    )
                    if consecutive_failures >= FAILURE_ABORT_THRESHOLD:
                        console.print(
                            f"[red]Abortando: {FAILURE_ABORT_THRESHOLD} falhas "
                            "consecutivas. Tente novamente mais tarde "
                            "(checkpoint preservado no ultimo page ok).[/red]"
                        )
                        break
                    # Try re-init on failure
                    try:
                        await client.reinit_session()
                    except Exception:
                        pass

            total = db.count()
            console.print()
            console.print(Panel(
                f"[green]+ Novas:[/green] {new_count}  |  "
                f"[yellow]~ Atualizadas:[/yellow] {updated_count}  |  "
                f"[red]x Paginas com falha:[/red] {failed_pages}  |  "
                f"[blue]# Total no DB:[/blue] {total:,}",
                title="Portal Compras CE -- Resultado",
                border_style="green",
            ))

    finally:
        db.close()


# -- enrich (detail) --------------------------------------------------


@app.command()
def enrich(
    limit: int = typer.Option(100, help="Limite de registros para enriquecer"),
    status: Optional[str] = typer.Option(None, help="Filtrar por status (ex: Finalizada)"),
    sistematica: Optional[str] = typer.Option("DISPENSA", help="Filtrar por sistematica (default: DISPENSA, que permite acesso direto)"),
    debug: bool = typer.Option(False, help="Debug logging"),
):
    """Enriquece registros com dados da pagina de detalhe."""
    setup_logging(debug)
    asyncio.run(_enrich(limit, status, sistematica))


async def _enrich(limit: int, status: Optional[str], sistematica: Optional[str]):
    settings = Settings()
    db = Database(settings.db_path)

    try:
        pubs = db.get_without_detail(limit=limit, status=status, sistematica=sistematica)
        if not pubs:
            console.print("[yellow]Nenhum registro para enriquecer.[/yellow]")
            return

        console.print(f"\n[bold blue]>> Enriquecendo {len(pubs)} registros...[/bold blue]\n")

        enriched = 0
        failed = 0

        async with LicitawebClient(settings) as client:
            for i, pub in enumerate(pubs):
                html = await client.fetch_detail(pub)
                if html is None:
                    failed += 1
                    continue

                lic = parse_detail_page(html, pub)
                if lic:
                    db.upsert(lic)
                    enriched += 1
                else:
                    failed += 1

                if (i + 1) % 50 == 0:
                    console.print(f"  [dim]Progress: {i+1}/{len(pubs)} ({enriched} enriched, {failed} failed)[/dim]")

        console.print(Panel(
            f"[green]Enriquecidos:[/green] {enriched}  |  "
            f"[red]Falhas:[/red] {failed}  |  "
            f"[blue]Total com detalhe:[/blue] {db.count_with_detail():,}",
            title="Enriquecimento de Detalhes",
            border_style="cyan",
        ))

    finally:
        db.close()


# -- search -----------------------------------------------------------


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

        console.print(f"\n[bold]Encontradas {len(results)} licitacoes para '{keyword}':[/bold]\n")

        table = Table(box=box.ROUNDED, show_lines=True)
        table.add_column("Publicacao", style="bold", width=12)
        table.add_column("Sistematica", width=15)
        table.add_column("Objeto", max_width=45)
        table.add_column("Orgao", style="green", width=25)
        table.add_column("Status", width=15)
        table.add_column("Vencedor", width=20)

        for r in results[:30]:
            obj = r["objeto"][:60] + "..." if len(r["objeto"]) > 60 else r["objeto"]
            orgao = (r["orgao"] or "")[:25]
            vencedor = (r["vencedor"] or "-")[:20]
            table.add_row(r["numero_publicacao"], (r["sistematica"] or "")[:15], obj, orgao, r["status"], vencedor)

        console.print(table)
    finally:
        db.close()


# -- stats -------------------------------------------------------------


@app.command()
def stats():
    """Estatisticas da base."""
    settings = Settings()
    db = Database(settings.db_path)

    try:
        s = db.stats()
        if s["total"] == 0:
            console.print("[yellow]Banco vazio. Execute 'sync' primeiro.[/yellow]")
            return

        console.print(f"\n[bold]Portal Compras CE -- {s['total']:,} licitacoes ({s['com_detalhe']:,} com detalhe)[/bold]\n")

        t_status = Table(title="Por Status", box=box.SIMPLE)
        t_status.add_column("Status", style="cyan")
        t_status.add_column("Qtde", justify="right", style="green")
        for st, count in s["by_status"].items():
            t_status.add_row(st or "(vazio)", f"{count:,}")
        console.print(t_status)

        t_sist = Table(title="Por Sistematica", box=box.SIMPLE)
        t_sist.add_column("Sistematica", style="cyan")
        t_sist.add_column("Qtde", justify="right", style="green")
        for sist, count in s["by_sistematica"].items():
            t_sist.add_row(sist or "(vazio)", f"{count:,}")
        console.print(t_sist)

        t_ano = Table(title="Por Ano", box=box.SIMPLE)
        t_ano.add_column("Ano", style="cyan")
        t_ano.add_column("Qtde", justify="right", style="green")
        for ano, count in s["by_ano"].items():
            t_ano.add_row(str(ano), f"{count:,}")
        console.print(t_ano)

        t_org = Table(title="Top Orgaos", box=box.SIMPLE)
        t_org.add_column("Orgao", style="cyan")
        t_org.add_column("Qtde", justify="right", style="green")
        for org, count in list(s["by_orgao"].items())[:10]:
            t_org.add_row(org or "(vazio)", f"{count:,}")
        console.print(t_org)

    finally:
        db.close()


# -- export ------------------------------------------------------------


@app.command()
def export(
    format: str = typer.Option("json", help="Formato: json, csv"),
    output: Optional[str] = typer.Option(None, help="Arquivo de saida"),
):
    """Exportar dados."""
    settings = Settings()
    db = Database(settings.db_path)

    try:
        if format == "csv":
            path = Path(output) if output else settings.data_dir / "licitacoes_ce.csv"
            count = db.export_csv(path)
        else:
            path = Path(output) if output else settings.data_dir / "licitacoes_ce.json"
            count = db.export_json(path)

        console.print(f"[green]Exportadas {count:,} licitacoes para {path}[/green]")
    finally:
        db.close()
