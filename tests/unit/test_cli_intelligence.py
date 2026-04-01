"""Testes para CLI principal do pacote licitabrasil."""

from typer.testing import CliRunner

from licitabrasil.cli.main import app

runner = CliRunner()


class TestCLIVersion:
    def test_version(self):
        result = runner.invoke(app, ["version"])
        assert result.exit_code == 0
        assert "LicitaBrasil" in result.output
        assert "0.2.0" in result.output


class TestCLIHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "scrape" in result.output
        assert "extract" in result.output
        assert "match" in result.output
        assert "gerar" in result.output

    def test_scrape_help(self):
        result = runner.invoke(app, ["scrape", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output
        assert "all" in result.output
        assert "status" in result.output

    def test_extract_help(self):
        result = runner.invoke(app, ["extract", "--help"])
        assert result.exit_code == 0
        assert "pdf" in result.output

    def test_match_help(self):
        result = runner.invoke(app, ["match", "--help"])
        assert result.exit_code == 0
        assert "run" in result.output

    def test_gerar_help(self):
        result = runner.invoke(app, ["gerar", "--help"])
        assert result.exit_code == 0
        assert "proposta" in result.output
        assert "declaracao" in result.output
        assert "checklist" in result.output


class TestCLIExtractValidation:
    def test_extract_arquivo_inexistente(self):
        result = runner.invoke(app, ["extract", "pdf", "/arquivo/inexistente.pdf"])
        assert result.exit_code == 1
        assert "nao encontrado" in result.output.lower() or "not found" in result.output.lower()

    def test_extract_arquivo_nao_pdf(self, tmp_path):
        txt_file = tmp_path / "teste.txt"
        txt_file.write_text("nao sou pdf")
        result = runner.invoke(app, ["extract", "pdf", str(txt_file)])
        assert result.exit_code == 1


class TestCLIScrapeStatus:
    def test_scrape_status_sem_scrapers(self):
        result = runner.invoke(app, ["scrape", "status"])
        assert result.exit_code == 0
        # Sem scrapers registrados, deve informar
        assert "nenhum" in result.output.lower() or "Nenhum" in result.output


class TestCLIMatchValidation:
    def test_match_sem_cnpj_e_perfil(self):
        result = runner.invoke(app, ["match", "run"])
        assert result.exit_code == 1
