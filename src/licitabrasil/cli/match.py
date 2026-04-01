"""CLI subcomando: licitabrasil match --cnpj <cnpj> [--min-score 0.6]."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.table import Table

from licitabrasil.cli._helpers import console, load_json_model, require_file, run_async
from licitabrasil.processors.matcher import (
    LicitacaoParaMatch,
    MatchEngine,
    PerfilEmpresa,
)

app = typer.Typer(no_args_is_help=True)


def _carregar_perfil(cnpj: str | None, perfil_path: Path | None) -> PerfilEmpresa:
    """Carrega perfil de empresa de arquivo JSON ou cria mínimo com CNPJ.

    Args:
        cnpj: CNPJ da empresa (usado se ``perfil_path`` não informado).
        perfil_path: Caminho para JSON com PerfilEmpresa completo.

    Returns:
        Instância validada de PerfilEmpresa.

    Raises:
        typer.BadParameter: Se nem CNPJ nem perfil forem informados.
    """
    if perfil_path:
        return load_json_model(perfil_path, PerfilEmpresa)
    if cnpj:
        return PerfilEmpresa(cnpj=cnpj, razao_social="(via CNPJ)")
    raise typer.BadParameter("Informe --cnpj ou --perfil")


def _carregar_licitacoes(dias: int) -> list[LicitacaoParaMatch]:
    """Carrega licitações dos últimos *dias* do banco para matching.

    Args:
        dias: Janela de tempo em dias (a partir de hoje).

    Returns:
        Lista de DTOs prontos para o MatchEngine.
    """
    async def _query():
        from datetime import datetime, timedelta
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from licitabrasil.database import get_session, dispose_engine
        from licitabrasil.models import Licitacao

        resultado = []
        async with get_session() as s:
            cutoff = datetime.now() - timedelta(days=dias)
            query = (
                select(Licitacao)
                .options(selectinload(Licitacao.orgao))
                .where(Licitacao.coletado_em >= cutoff)
                .order_by(Licitacao.coletado_em.desc())
                .limit(1000)
            )
            rows = (await s.execute(query)).scalars().all()

            for r in rows:
                cnaes = []
                if r.cnaes_detectados:
                    try:
                        cnaes = json.loads(r.cnaes_detectados)
                    except (json.JSONDecodeError, TypeError):
                        pass

                resultado.append(LicitacaoParaMatch(
                    id=str(r.id),
                    objeto=r.objeto,
                    cnae=cnaes,
                    valor_estimado=r.valor_estimado,
                    uf=r.orgao.uf if r.orgao else None,
                    municipio=r.orgao.municipio if r.orgao else None,
                    orgao=r.orgao.nome if r.orgao else "",
                ))

        await dispose_engine()
        return resultado

    return run_async(_query())


@app.command("run")
def run_match(
    cnpj: str = typer.Option(None, "--cnpj", "-c", help="CNPJ da empresa para matching"),
    perfil: Path = typer.Option(None, "--perfil", "-p", help="Arquivo JSON com PerfilEmpresa"),
    dias: int = typer.Option(30, "--dias", "-d", help="Considerar licitacoes dos ultimos N dias"),
    min_score: float = typer.Option(0.5, "--min-score", help="Score minimo (0.0 a 1.0)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximo de resultados"),
    output: str = typer.Option("rich", "--output", "-o", help="Formato: rich, json"),
):
    """Calcular matching entre empresa e licitacoes.

    Carrega o perfil da empresa (JSON ou CNPJ minimo), busca licitações
    recentes no banco e aplica o MatchEngine com 5 critérios ponderados
    (CNAE, keywords TF-IDF, valor, região, histórico).
    """
    if not cnpj and not perfil:
        console.print("[red]Informe --cnpj ou --perfil[/red]")
        raise typer.Exit(1)

    if perfil:
        require_file(perfil, extensions=[".json"])

    empresa = _carregar_perfil(cnpj, perfil)
    console.print(f"[bold blue]Matching:[/bold blue] {empresa.razao_social} ({empresa.cnpj})")
    console.print(f"  Ultimos {dias} dias, score >= {min_score}")

    licitacoes = _carregar_licitacoes(dias)
    console.print(f"  {len(licitacoes)} licitacoes carregadas do banco")

    if not licitacoes:
        console.print("[yellow]Nenhuma licitacao encontrada no periodo.[/yellow]")
        return

    engine = MatchEngine()
    matches = engine.calcular_matches(empresa, licitacoes, min_score=min_score)
    matches = matches[:limit]

    if output == "json":
        console.print(json.dumps([m.model_dump() for m in matches], indent=2, default=str))
        return

    if not matches:
        console.print("[yellow]Nenhum match acima do score minimo.[/yellow]")
        return

    console.print(f"\n[bold green]{len(matches)} matches encontrados:[/bold green]\n")
    table = Table()
    table.add_column("Score", style="bold")
    table.add_column("Rec.", style="bold")
    table.add_column("Objeto", max_width=50)
    table.add_column("CNAE")
    table.add_column("KW")
    table.add_column("Valor")
    table.add_column("Regiao")

    for m in matches:
        style = "green" if m.recomendacao == "alta" else "yellow" if m.recomendacao == "media" else "dim"
        table.add_row(
            f"[{style}]{m.score_total:.1%}[/{style}]",
            f"[{style}]{m.recomendacao}[/{style}]",
            next((lic.objeto[:50] for lic in licitacoes if lic.id == m.licitacao_id), "?"),
            f"{m.scores.get('cnae', 0):.0%}",
            f"{m.scores.get('keywords', 0):.0%}",
            f"{m.scores.get('valor', 0):.0%}",
            f"{m.scores.get('regiao', 0):.0%}",
        )

    console.print(table)
