"""CLI subcomando: licitabrasil scrape <portal> [--dias N]."""

from __future__ import annotations

import typer
from rich.table import Table

from licitabrasil.cli._helpers import console, run_async
from licitabrasil.scrapers.registry import get_scraper, list_scrapers

app = typer.Typer(no_args_is_help=True)


@app.command("run")
def run(
    portal: str = typer.Argument(help="Nome do portal (ex: maceio, natal, ceara)"),
    dias: int = typer.Option(7, "--dias", "-d", help="Buscar licitações dos últimos N dias"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Logging detalhado"),
):
    """Executar scraper de um portal específico.

    Instancia o scraper registrado para *portal*, executa a coleta
    dos últimos *dias* e exibe o total de licitações encontradas.
    """
    import logging
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO)

    async def _run():
        scraper = get_scraper(portal)
        async with scraper:
            console.print(f"[bold blue]Coletando licitações de {portal}...[/bold blue] (últimos {dias} dias)")
            results = await scraper.buscar_licitacoes(dias=dias)
            console.print(f"[green]✓[/green] {len(results)} licitações encontradas")
            return results

    run_async(_run())


@app.command("all")
def run_all(
    dias: int = typer.Option(7, "--dias", "-d", help="Buscar licitações dos últimos N dias"),
):
    """Executar todos os scrapers registrados sequencialmente.

    Itera sobre todos os portais em ``list_scrapers()`` e executa
    a coleta de cada um. Erros são capturados e reportados sem
    interromper a execução dos demais.
    """
    portais = list_scrapers()
    if not portais:
        console.print("[yellow]Nenhum scraper registrado.[/yellow]")
        return

    async def _run_all():
        for portal_name in portais:
            console.print(f"\n[bold blue]→ {portal_name}[/bold blue]")
            try:
                scraper = get_scraper(portal_name)
                async with scraper:
                    results = await scraper.buscar_licitacoes(dias=dias)
                    console.print(f"  [green]✓[/green] {len(results)} licitações")
            except Exception as e:
                console.print(f"  [red]✗[/red] Erro: {e}")

    run_async(_run_all())


@app.command("status")
def status():
    """Health check de todos os scrapers registrados.

    Chama ``health_check()`` de cada scraper e monta uma tabela
    com status HTTP, mensagem de erro e indicador visual.
    """
    portais = list_scrapers()
    if not portais:
        console.print("[yellow]Nenhum scraper registrado.[/yellow]")
        return

    async def _check():
        table = Table(title="Status dos Scrapers")
        table.add_column("Portal", style="cyan")
        table.add_column("Status")
        table.add_column("HTTP")
        table.add_column("Erro")

        for portal_name in portais:
            scraper = get_scraper(portal_name)
            async with scraper:
                result = await scraper.health_check()
                status_style = "green" if result["status"] == "ok" else "red"
                table.add_row(
                    portal_name,
                    f"[{status_style}]{result['status']}[/{status_style}]",
                    str(result.get("http_code", "-")),
                    result.get("error", "-"),
                )
        console.print(table)

    run_async(_check())
