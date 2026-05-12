"""CLI principal — ponto de entrada `licitabrasil`."""

import typer

from licitabrasil.cli.alert import app as alert_app
from licitabrasil.cli.extract import app as extract_app
from licitabrasil.cli.generate import app as generate_app
from licitabrasil.cli.match import app as match_app
from licitabrasil.cli.monitor import app as monitor_app
from licitabrasil.cli.scrape import app as scrape_app

app = typer.Typer(
    name="licitabrasil",
    help="LicitaBrasil — Plataforma de Inteligência em Licitações Públicas",
    no_args_is_help=True,
)

app.add_typer(scrape_app, name="scrape", help="Coletar licitações dos portais")
app.add_typer(extract_app, name="extract", help="Extrair dados de editais (PDF)")
app.add_typer(match_app, name="match", help="Matching empresa × licitações")
app.add_typer(generate_app, name="gerar", help="Gerar propostas e declarações")
app.add_typer(alert_app, name="alertas", help="Gerenciar e executar alertas")
app.add_typer(monitor_app, name="monitor", help="Monitor de prazos críticos (Argus)")


@app.command()
def version():
    """Mostra a versão do LicitaBrasil."""
    from licitabrasil import __version__
    typer.echo(f"LicitaBrasil v{__version__}")


if __name__ == "__main__":
    app()
