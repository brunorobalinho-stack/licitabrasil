"""CLI subcomando: licitabrasil gerar proposta|declaracao."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import typer

from licitabrasil.cli._helpers import console, load_json_model, require_file, run_async
from licitabrasil.generators.proposta import (
    DadosEmpresa,
    DadosLicitacao,
    ItemProposta,
    PropostaGenerator,
)

app = typer.Typer(no_args_is_help=True)


def _buscar_licitacao(licitacao_id: int, *, load_lotes: bool = False):
    """Busca licitacao no banco por ID, com eager-load de relacionamentos.

    Args:
        licitacao_id: PK da licitação.
        load_lotes: Se ``True``, carrega também os lotes (para proposta de preços).

    Returns:
        Instância ``Licitacao`` ou ``None`` se não encontrada.
    """
    async def _query():
        from sqlalchemy.orm import selectinload
        from licitabrasil.database import get_session, dispose_engine
        from licitabrasil.models import Licitacao

        options = [selectinload(Licitacao.orgao)]
        if load_lotes:
            options.append(selectinload(Licitacao.lotes))

        async with get_session() as s:
            lic = await s.get(Licitacao, licitacao_id, options=options)
        await dispose_engine()
        return lic

    return run_async(_query())


def _require_licitacao(licitacao_id: int, *, load_lotes: bool = False):
    """Busca licitação ou aborta CLI se não encontrada.

    Args:
        licitacao_id: PK da licitação.
        load_lotes: Se ``True``, carrega lotes junto.

    Returns:
        Instância ``Licitacao``.

    Raises:
        typer.Exit: Se a licitação não existir no banco.
    """
    lic = _buscar_licitacao(licitacao_id, load_lotes=load_lotes)
    if not lic:
        console.print(f"[red]Licitacao {licitacao_id} nao encontrada no banco.[/red]")
        raise typer.Exit(1)
    return lic


@app.command("proposta")
def gerar_proposta(
    licitacao_id: int = typer.Option(..., "--licitacao", "-l", help="ID da licitacao"),
    empresa: Path = typer.Option(..., "--empresa", "-e", help="Arquivo JSON com dados da empresa"),
    output: Path = typer.Option("proposta.docx", "--output", "-o", help="Arquivo de saida"),
):
    """Gerar proposta de precos em DOCX.

    Carrega dados da empresa de um JSON e a licitação do banco,
    monta a lista de itens a partir dos lotes e gera o DOCX
    usando template ou fallback programático.
    """
    require_file(empresa, extensions=[".json"])
    dados_empresa = load_json_model(empresa, DadosEmpresa)
    lic = _require_licitacao(licitacao_id, load_lotes=True)

    dados_lic = DadosLicitacao(
        numero=lic.numero,
        orgao=lic.orgao.nome if lic.orgao else "",
        modalidade=lic.modalidade.value if lic.modalidade else "",
        objeto=lic.objeto,
        data_abertura=lic.data_abertura.strftime("%d/%m/%Y") if lic.data_abertura else "",
    )

    itens = [
        ItemProposta(
            numero=lote.numero,
            descricao=lote.descricao,
            unidade=lote.unidade or "UN",
            quantidade=lote.quantidade or Decimal(1),
            valor_unitario=lote.valor_unitario or Decimal(0),
        )
        for lote in lic.lotes
    ]

    if not itens:
        console.print("[yellow]Licitacao sem lotes cadastrados. Gerando com campo em branco.[/yellow]")
        itens = [ItemProposta(numero=1, descricao=lic.objeto[:200], unidade="SV", quantidade=Decimal(1), valor_unitario=Decimal(0))]

    generator = PropostaGenerator()
    result = generator.gerar_proposta_preco(dados_empresa, dados_lic, itens, output)
    console.print(f"[green]Proposta gerada:[/green] {result}")


@app.command("declaracao")
def gerar_declaracao(
    tipo: str = typer.Argument(help="Tipo: me-epp, fato-impeditivo, menor"),
    empresa: Path = typer.Option(..., "--empresa", "-e", help="Arquivo JSON com dados da empresa"),
    output: Path = typer.Option(None, "--output", "-o", help="Arquivo de saida"),
):
    """Gerar declaracao padrao em DOCX.

    Tipos suportados: me-epp, fato-impeditivo, menor, independente.
    """
    require_file(empresa, extensions=[".json"])
    dados_empresa = load_json_model(empresa, DadosEmpresa)

    if not output:
        output = Path(f"declaracao_{tipo.replace('-', '_')}.docx")

    generator = PropostaGenerator()
    result = generator.gerar_declaracao(tipo, dados_empresa, output)
    console.print(f"[green]Declaracao gerada:[/green] {result}")


@app.command("checklist")
def gerar_checklist(
    licitacao_id: int = typer.Option(..., "--licitacao", "-l", help="ID da licitacao"),
):
    """Listar documentos necessarios para uma licitacao."""
    lic = _require_licitacao(licitacao_id)

    console.print(f"[bold]Checklist para licitacao:[/bold] {lic.numero}")
    console.print(f"[bold]Orgao:[/bold] {lic.orgao.nome if lic.orgao else 'N/A'}")
    console.print(f"[bold]Modalidade:[/bold] {lic.modalidade.value}")

    docs = [
        "Proposta de precos",
        "Declaracao de ME/EPP (se aplicavel)",
        "Declaracao de inexistencia de fato impeditivo",
        "Declaracao de nao emprego de menor",
        "Contrato social / Estatuto",
        "Certidao negativa de debitos federais (CND)",
        "Certidao de regularidade FGTS (CRF)",
        "Certidao negativa de debitos trabalhistas (CNDT)",
        "Certidao negativa de debitos estaduais",
        "Certidao negativa de debitos municipais",
        "Balanco patrimonial do ultimo exercicio",
        "Atestado de capacidade tecnica",
    ]

    console.print("\n[bold green]Documentos necessarios:[/bold green]")
    for i, d in enumerate(docs, 1):
        console.print(f"  {i:2d}. [ ] {d}")
