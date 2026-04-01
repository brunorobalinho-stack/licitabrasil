"""CLI subcomando: licitabrasil alertas.

TODO: Implementar
- licitabrasil alertas criar
- licitabrasil alertas listar
- licitabrasil alertas executar
"""

from __future__ import annotations

import typer
from rich.console import Console

app = typer.Typer(no_args_is_help=True)
console = Console()


@app.command("listar")
def listar_alertas():
    """Listar alertas cadastrados."""
    console.print("[yellow]Comando ainda nao implementado.[/yellow]")


@app.command("executar")
def executar_alertas():
    """Executar motor de alertas manualmente."""
    console.print("[yellow]Comando ainda nao implementado.[/yellow]")
