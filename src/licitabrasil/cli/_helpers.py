"""Utilidades compartilhadas pelos subcomandos CLI.

Centraliza padrões repetidos: validação de caminhos, carregamento
de JSON para Pydantic models, e wrapper para execução de coroutines
com sessão de banco de dados.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import TypeVar

import typer
from pydantic import BaseModel
from rich.console import Console

console = Console()

T = TypeVar("T", bound=BaseModel)


def require_file(path: Path, *, extensions: list[str] | None = None) -> None:
    """Valida que *path* existe e, opcionalmente, possui extensão esperada.

    Imprime mensagem de erro formatada e aborta o CLI com código 1.

    Args:
        path: Caminho do arquivo a verificar.
        extensions: Lista de extensões permitidas (ex: [".pdf", ".docx"]).
            Se ``None``, aceita qualquer extensão.

    Raises:
        typer.Exit: Se o arquivo não existir ou a extensão não for válida.
    """
    if not path.exists():
        console.print(f"[red]Arquivo nao encontrado: {path}[/red]")
        raise typer.Exit(1)
    if extensions and path.suffix.lower() not in extensions:
        console.print(f"[red]Extensao invalida: {path.suffix} (esperado: {', '.join(extensions)})[/red]")
        raise typer.Exit(1)


def load_json_model(path: Path, model_cls: type[T]) -> T:
    """Carrega arquivo JSON e instancia um Pydantic model.

    Args:
        path: Caminho para o arquivo JSON.
        model_cls: Classe Pydantic para deserialização.

    Returns:
        Instância validada do model.

    Raises:
        typer.Exit: Se o arquivo não existir ou o JSON for inválido.
    """
    require_file(path, extensions=[".json"])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        console.print(f"[red]JSON invalido em {path}: {exc}[/red]")
        raise typer.Exit(1) from exc
    return model_cls(**data)


def run_async(coro):
    """Executa uma coroutine no event loop síncrono.

    Wrapper fino sobre ``asyncio.run()`` para manter consistência
    e permitir futura troca por uvloop ou similar.

    Args:
        coro: Coroutine a executar.

    Returns:
        Resultado da coroutine.
    """
    return asyncio.run(coro)
