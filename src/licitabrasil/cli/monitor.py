"""CLI subcomando: ``licitabrasil monitor prazos``.

Cruza dados de todos os scrapers locais e gera briefing de prazos
priorizado por urgência (uso primário: scheduled task Argus).
"""

from __future__ import annotations

import json
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from licitabrasil.monitoring import (
    PrazoItem,
    Urgencia,
    coletar_prazos,
    formatar_briefing,
)
from licitabrasil.monitoring.prazos import resumo_por_fonte


app = typer.Typer(no_args_is_help=True)
console = Console()


URGENCIA_COLOR = {
    Urgencia.VENCIDO: "red on white",
    Urgencia.CRITICO: "bold red",
    Urgencia.ATENCAO: "bold yellow",
    Urgencia.PLANEJAMENTO: "cyan",
}


@app.command()
def prazos(
    dias: int = typer.Option(30, "--dias", "-d", help="Horizonte de busca em dias"),
    argus: bool = typer.Option(False, "--argus", help="Atalho para --tag cliente-argus"),
    tag: Optional[str] = typer.Option(None, "--tag", help="Filtrar scrapers por tag"),
    uf: Optional[str] = typer.Option(None, "--uf", help="Filtrar por UF"),
    fonte: Optional[list[str]] = typer.Option(None, "--fonte", help="Restringir a fontes específicas"),
    include_vencidos: bool = typer.Option(False, "--vencidos/--no-vencidos"),
    formato: str = typer.Option("rich", "--formato", "-f", help="rich | markdown | json"),
):
    """Lista prazos críticos consolidados de todos os scrapers."""
    if argus:
        tag = "cliente-argus"

    items = coletar_prazos(
        dias=dias,
        fontes=fonte,
        tag=tag,
        uf=uf,
        include_vencidos=include_vencidos,
    )

    if formato == "markdown":
        console.print(formatar_briefing(items))
        return

    if formato == "json":
        payload = [
            {
                "fonte": i.fonte,
                "id": i.identificador,
                "objeto": i.objeto,
                "orgao": i.orgao,
                "modalidade": i.modalidade,
                "fase": i.fase_ou_situacao,
                "prazo": i.prazo.isoformat(),
                "dias_restantes": i.dias_restantes,
                "urgencia": i.urgencia.value,
                "url": i.url,
            }
            for i in items
        ]
        console.print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    # formato 'rich' (padrão)
    if not items:
        console.print("[yellow]Nenhum prazo encontrado nas fontes consultadas.[/yellow]")
        return

    table = Table(title=f"Prazos próximos {dias} dias — {len(items)} itens")
    table.add_column("Urg.", style="bold")
    table.add_column("Fonte", style="cyan")
    table.add_column("ID")
    table.add_column("Prazo")
    table.add_column("d-", justify="right")
    table.add_column("Órgão / Unidade", overflow="fold")
    table.add_column("Objeto", overflow="fold")
    table.add_column("Fase/Situação", style="dim")

    for it in items:
        color = URGENCIA_COLOR.get(it.urgencia, "white")
        table.add_row(
            f"[{color}]{it.urgencia.value[:4]}[/{color}]",
            it.fonte,
            it.identificador[:30],
            it.prazo.strftime("%d/%m %H:%M"),
            str(it.dias_restantes),
            it.orgao[:40],
            it.objeto[:60],
            it.fase_ou_situacao[:25],
        )
    console.print(table)

    # Resumo
    summary = resumo_por_fonte(items)
    if summary:
        sum_table = Table(title="Resumo por fonte")
        sum_table.add_column("Fonte", style="cyan")
        for urg in (Urgencia.VENCIDO, Urgencia.CRITICO, Urgencia.ATENCAO, Urgencia.PLANEJAMENTO):
            sum_table.add_column(urg.value[:6], justify="right")
        sum_table.add_column("Total", justify="right", style="bold")
        for fonte_name, counts in summary.items():
            total = sum(counts.values())
            sum_table.add_row(
                fonte_name,
                str(counts.get("VENCIDO", 0)),
                str(counts.get("CRITICO", 0)),
                str(counts.get("ATENCAO", 0)),
                str(counts.get("PLANEJAMENTO", 0)),
                str(total),
            )
        console.print(sum_table)


@app.command()
def briefing(
    dias: int = typer.Option(7, "--dias", "-d"),
    argus: bool = typer.Option(True, "--argus/--all"),
    saida: Optional[str] = typer.Option(None, "--saida", "-o", help="Salvar briefing em arquivo .md"),
):
    """Gera briefing em Markdown (consumido pela scheduled task Argus)."""
    items = coletar_prazos(
        dias=dias,
        tag="cliente-argus" if argus else None,
        include_vencidos=True,
    )
    md = formatar_briefing(items)
    if saida:
        from pathlib import Path
        Path(saida).write_text(md, encoding="utf-8")
        console.print(f"[green]Briefing salvo em {saida}[/green]")
    else:
        console.print(md)
