"""CLI subcomando: licitabrasil extract <pdf_path>."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.table import Table

from licitabrasil.cli._helpers import console, require_file
from licitabrasil.processors.extractor import EditalExtractor

app = typer.Typer(no_args_is_help=True)


@app.command("pdf")
def extract_pdf(
    path: Path = typer.Argument(help="Caminho para o arquivo PDF do edital"),
    output: str = typer.Option("rich", "--output", "-o", help="Formato de saida: rich, json"),
    salvar: bool = typer.Option(False, "--salvar", "-s", help="Salvar no banco de dados"),
):
    """Extrair dados estruturados de um edital em PDF.

    Le o PDF indicado, identifica secoes do edital (objeto, valor,
    habilitacao, prazos) via regex e retorna resultado estruturado
    no formato rich (tabela) ou JSON.
    """
    require_file(path, extensions=[".pdf"])

    console.print(f"[bold blue]Extraindo dados de:[/bold blue] {path}")

    extractor = EditalExtractor()
    resultado = extractor.extrair(path)

    if output == "json":
        console.print(resultado.model_dump_json(indent=2))
        return

    # Rich output
    console.print(f"\n[bold]Arquivo:[/bold] {resultado.arquivo}")
    console.print(f"[bold]Paginas:[/bold] {resultado.total_paginas}")

    if resultado.objeto:
        console.print(f"\n[bold green]Objeto:[/bold green] {resultado.objeto}")
    if resultado.valor_estimado:
        console.print(f"[bold green]Valor estimado:[/bold green] R$ {resultado.valor_estimado:,.2f}")
    if resultado.data_abertura:
        console.print(f"[bold green]Data abertura:[/bold green] {resultado.data_abertura.strftime('%d/%m/%Y %H:%M')}")
    if resultado.criterio_julgamento:
        console.print(f"[bold green]Criterio:[/bold green] {resultado.criterio_julgamento}")
    if resultado.exclusiva_me_epp:
        console.print("[bold yellow]Exclusiva ME/EPP:[/bold yellow] Sim")

    if resultado.requisitos_habilitacao:
        console.print(f"\n[bold]Requisitos de habilitacao ({len(resultado.requisitos_habilitacao)}):[/bold]")
        for req in resultado.requisitos_habilitacao[:10]:
            console.print(f"  - {req}")

    if resultado.prazos:
        console.print("\n[bold]Prazos:[/bold]")
        for key, val in resultado.prazos.items():
            console.print(f"  {key}: {val}")

    if resultado.secoes:
        table = Table(title="\nSecoes identificadas")
        table.add_column("Tipo", style="cyan")
        table.add_column("Pagina")
        table.add_column("Confianca")
        table.add_column("Preview", max_width=60)
        for s in resultado.secoes:
            table.add_row(
                s.tipo,
                str(s.pagina_inicio),
                f"{s.confianca:.0%}",
                s.texto[:60].replace("\n", " ") + "...",
            )
        console.print(table)

    if salvar:
        console.print("\n[yellow]--salvar: persistencia no DB sera implementada em breve[/yellow]")
