"""CLI subcomando: ``licitabrasil scrape``.

Operações suportadas:

* ``list``       — lista scrapers registrados com metadados
* ``status``     — health check dos portais (GET na base_url)
* ``stats``      — estatísticas locais (contagem por SQLite)
* ``run <name>`` — executa um scraper específico
* ``all``        — executa todos os scrapers registrados
"""

from __future__ import annotations

import asyncio
from typing import Optional

import typer
from rich.table import Table

from licitabrasil.cli._helpers import console, run_async
from licitabrasil.scrapers.registry import (
    ScraperInfo,
    db_stats,
    filter_by,
    get_scraper,
    health_check,
    list_scrapers,
    run_scraper,
)

app = typer.Typer(no_args_is_help=True)


# ── list ──────────────────────────────────────────────────────────────


@app.command("list")
def list_cmd(
    esfera: Optional[str] = typer.Option(None, "--esfera", "-e", help="federal/estadual/municipal/agregador"),
    uf: Optional[str] = typer.Option(None, "--uf", help="Filtrar por UF (ex: PE, SP)"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtrar por tag (ex: cliente-argus)"),
    incluir_disabled: bool = typer.Option(
        False, "--all", help="Inclui scrapers com enabled=False (mostra motivo)"
    ),
):
    """Lista scrapers registrados."""
    scrapers = filter_by(esfera=esfera, uf=uf, tag=tag, include_disabled=incluir_disabled)
    if not scrapers:
        console.print("[yellow]Nenhum scraper encontrado com esses filtros.[/yellow]")
        return

    titulo = f"Scrapers LicitaBrasil ({len(scrapers)}" + (", incluindo disabled" if incluir_disabled else "") + ")"
    table = Table(title=titulo, show_lines=False)
    table.add_column("Nome", style="cyan", no_wrap=True)
    table.add_column("Esfera", style="magenta")
    table.add_column("UF", justify="center")
    table.add_column("Portal", style="green")
    table.add_column("Descrição", style="dim", overflow="fold")

    for s in scrapers:
        nome = s.name if s.enabled else f"[red]{s.name} (DISABLED)[/red]"
        descricao = s.description if s.enabled else f"DISABLED — {s.disabled_motivo or 'sem motivo registrado'}"
        table.add_row(
            nome,
            s.esfera,
            s.uf or "—",
            s.portal,
            descricao[:80] + ("…" if len(descricao) > 80 else ""),
        )
    console.print(table)


# ── status ────────────────────────────────────────────────────────────


@app.command("status")
def status_cmd(
    esfera: Optional[str] = typer.Option(None, "--esfera", "-e", help="Filtrar por esfera"),
    uf: Optional[str] = typer.Option(None, "--uf", help="Filtrar por UF"),
    timeout: float = typer.Option(10.0, "--timeout", help="Timeout HTTP em segundos"),
):
    """Health check de todos os scrapers (request GET na URL base)."""
    scrapers = filter_by(esfera=esfera, uf=uf)
    if not scrapers:
        console.print("[yellow]Nenhum scraper para checar.[/yellow]")
        return

    async def _check():
        tasks = [health_check(s, timeout=timeout) for s in scrapers]
        return await asyncio.gather(*tasks)

    results = run_async(_check())

    table = Table(title="Status dos Portais")
    table.add_column("Scraper", style="cyan")
    table.add_column("Status")
    table.add_column("HTTP", justify="center")
    table.add_column("Latência (s)", justify="right")
    table.add_column("Erro", style="dim", overflow="fold")

    for r in results:
        status_color = {"ok": "green", "degraded": "yellow", "offline": "red"}.get(
            r["status"], "white"
        )
        table.add_row(
            r["name"],
            f"[{status_color}]{r['status']}[/{status_color}]",
            str(r.get("http_code") or "—"),
            str(r.get("elapsed_s", "—")),
            r.get("error", "—")[:60],
        )
    console.print(table)


# ── stats (DB) ────────────────────────────────────────────────────────


@app.command("stats")
def stats_cmd():
    """Estatísticas locais — contagem por SQLite de cada scraper."""
    scrapers = list_scrapers()
    table = Table(title="Estatísticas locais (SQLite)")
    table.add_column("Scraper", style="cyan")
    table.add_column("Total", justify="right")
    table.add_column("Tamanho (MB)", justify="right")
    table.add_column("Última coleta", style="dim")
    table.add_column("DB", style="dim", overflow="fold")

    grand_total = 0
    for s in scrapers:
        st = db_stats(s)
        total = st.get("total", 0)
        grand_total += total
        table.add_row(
            s.name,
            str(total) if st.get("exists") else "[red]—[/red]",
            str(st.get("db_size_mb", "—")),
            str(st.get("last_collected") or "—"),
            str(st.get("db_path", "—")),
        )

    table.add_row("", "", "", "", "", style="dim")
    table.add_row(
        "[bold]TOTAL[/bold]",
        f"[bold]{grand_total:,}[/bold]",
        "",
        "",
        "",
    )
    console.print(table)


# ── run ───────────────────────────────────────────────────────────────


@app.command("run")
def run_cmd(
    name: str = typer.Argument(help="Nome do scraper (use `list` para ver disponíveis)"),
    args: Optional[list[str]] = typer.Argument(
        None,
        help="Argumentos extras passados ao CLI do scraper (ex: sync --max-pages 5)",
    ),
    timeout: Optional[int] = typer.Option(None, "--timeout", help="Timeout em segundos"),
):
    """Executa um scraper específico como subprocess."""
    info = get_scraper(name)
    console.print(f"\n[bold blue]▶ Executando {info.name}[/bold blue] ({info.label})")
    console.print(f"[dim]Módulo: python -m {info.module}[/dim]\n")

    result = run_scraper(info, args=list(args) if args else None, timeout=timeout)
    if result.returncode == 0:
        console.print(f"\n[green]✓[/green] {info.name} finalizado com sucesso.")
    else:
        console.print(f"\n[red]✗[/red] {info.name} retornou código {result.returncode}.")
        raise typer.Exit(result.returncode)


# ── all ───────────────────────────────────────────────────────────────


@app.command("all")
def run_all_cmd(
    esfera: Optional[str] = typer.Option(None, "--esfera", "-e", help="Filtrar por esfera"),
    uf: Optional[str] = typer.Option(None, "--uf", help="Filtrar por UF"),
    args: Optional[list[str]] = typer.Option(
        None, "--arg", help="Argumento repetível passado a todos os scrapers"
    ),
    continue_on_error: bool = typer.Option(
        True, "--continue/--stop", help="Continuar mesmo se um scraper falhar"
    ),
):
    """Executa todos os scrapers (com filtro opcional)."""
    scrapers = filter_by(esfera=esfera, uf=uf)
    if not scrapers:
        console.print("[yellow]Nenhum scraper para executar com esses filtros.[/yellow]")
        return

    successes: list[str] = []
    failures: list[tuple[str, int]] = []

    for s in scrapers:
        console.print(f"\n[bold blue]▶ {s.name}[/bold blue] ({s.label})")
        try:
            result = run_scraper(s, args=list(args) if args else None)
            if result.returncode == 0:
                successes.append(s.name)
                console.print(f"[green]  ✓[/green] OK")
            else:
                failures.append((s.name, result.returncode))
                console.print(f"[red]  ✗[/red] código {result.returncode}")
                if not continue_on_error:
                    break
        except Exception as exc:
            failures.append((s.name, -1))
            console.print(f"[red]  ✗[/red] exception: {exc}")
            if not continue_on_error:
                break

    console.print(
        f"\n[bold]Resumo:[/bold] [green]{len(successes)} OK[/green] / "
        f"[red]{len(failures)} falha(s)[/red]"
    )
