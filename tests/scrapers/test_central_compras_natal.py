"""Testes para o scraper Central de Compras de Natal/RN."""

import tempfile
from pathlib import Path

import pytest

from scrapers.central_compras_natal.config import Settings, MODALIDADES
from scrapers.central_compras_natal.models import LicitacaoNatal
from scrapers.central_compras_natal.parser import parse_listing_page, parse_total_pages, parse_detail_page
from scrapers.central_compras_natal.storage import Storage


# ── Fixtures ─────────────────────────────────────


LISTING_HTML = """
<html>
<head><meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1"></head>
<body>
<form id="formulario" method="post">
<input type="hidden" name="mod" value="pregao-eletronico">
<input type="hidden" name="pagina" id="pagina" value="1">
<div class="CSSTableGenerator">
<table align="center">
<tr bgcolor="#bbb">
    <th>Licitacao</th><th>Processo</th><th>Tipo Licitacao</th><th>Orgao</th><th>Data</th><th>Objeto</th>
</tr>
<tr>
    <td width="10%" bgcolor="#fff"><a href="?mod=pregao-eletronico&id=2292">91.004/2026</a></td>
    <td width="10%" bgcolor="#fff">20251097616-SEMSUR</td>
    <td width="10%" bgcolor="#fff">Menor Preco</td>
    <td width="10%" bgcolor="#fff">Secretaria Municipal de Administracao</td>
    <td width="10%" bgcolor="#fff">24/02/2026</td>
    <td width="50%" bgcolor="#fff">REGISTRO DE PRECOS para fornecimento de ferramentas.</td>
</tr>
    <td width="10%" bgcolor="#d0ebff"><a href="?mod=pregao-eletronico&id=2290">91.012/2026</a></td>
    <td width="10%" bgcolor="#d0ebff">20250195340-SME</td>
    <td width="10%" bgcolor="#d0ebff">Menor Preco</td>
    <td width="10%" bgcolor="#d0ebff">Secretaria Municipal de Administracao</td>
    <td width="10%" bgcolor="#d0ebff">20/02/2026</td>
    <td width="50%" bgcolor="#d0ebff">Servico de nutricao para atendimento escolar.</td>
</tr>
<tr>
<td align="center" colspan="6">
    <strong class="texto_paginacao_pgatual">1</strong>
    <a href="#" onclick="document.getElementById('pagina').value=2;document.getElementById('formulario').submit();" class="texto_paginacao">2</a>
    <a href="#" onclick="document.getElementById('pagina').value=3;document.getElementById('formulario').submit();" class="texto_paginacao">3</a>
    Pag.: 1 2 3
</td>
</tr>
</table>
</div>
</form>
</body>
</html>
"""


DETAIL_HTML = """
<html>
<head><meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1"></head>
<body>
<div id="call">
<h1>Detalhamento da Licitação</h1>
<table>
<tr><th>Nr.Licitação</th><td>91.004/2026</td><th>Nr.Processo</th><td>20251097616-SEMSUR</td></tr>
<tr><th>Modalidade</th><td>Pregão Eletrônico</td><th>Tipo Licitação</th><td>Menor Preço</td></tr>
<tr><th>Titulo</th><td>Aquisição de ferramentas.</td></tr>
<tr><th>Secretaria Licitante</th><td>Secretaria Municipal de Administração</td></tr>
<tr><th>Objeto</th><td>REGISTRO DE PREÇOS para fornecimento de ferramentas conforme edital.</td></tr>
<tr><th>Registro Preço</th><td>Sim</td></tr>
<tr><th>Local Abertura</th><td>www.gov.br/compras/pt-br</td><th>Data Abertura</th><td>09/03/2026</td></tr>
</table>

<table>
<tr><th colspan="2">Documentos Relacionados</th></tr>
<tr><th>Documento</th><th>Responsável</th></tr>
<tr><td><a href="https://www2.natal.rn.gov.br/_anexos/compras/anexo_num_4450.pdf">EDITAL P.E. 91.004/2026</a></td><td>Rossana Figueiredo</td></tr>
</table>

<table>
<tr><th colspan="6">Histórico</th></tr>
<tr><th>Data</th><th>Fase</th><th>Detalhe</th><th>Unidade Orçam.</th><th>Dotação Orçam.</th><th>Arquivo</th></tr>
<tr><td>24/02/2026</td><td>Publicação</td><td>A publicação do aviso de licitação.</td><td>00000</td><td>00000</td><td><a href="https://www2.natal.rn.gov.br/_anexos/compras/fase_num_2246.pdf">Baixar</a></td></tr>
</table>

<table>
<tr><th colspan="3">Licitantes</th></tr>
<tr><th>Nome</th><th>Observação</th><th>Situação</th></tr>
<tr><td>EMPRESA XYZ LTDA</td><td>ME</td><td>Habilitada</td></tr>
<tr><td>FORNECEDORA ABC S.A.</td><td></td><td>Desclassificada</td></tr>
</table>
</div>
</body>
</html>
"""


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "test.db")
        yield db
        db.close()


# ── Parser Tests ─────────────────────────────────


class TestParseListingPage:
    def test_parses_rows(self):
        items = parse_listing_page(LISTING_HTML, "pregao-eletronico", "Pregão Eletrônico")
        assert len(items) == 2

    def test_first_item_fields(self):
        items = parse_listing_page(LISTING_HTML, "pregao-eletronico", "Pregão Eletrônico")
        item = items[0]
        assert item.numero_licitacao == "91.004/2026"
        assert item.numero_processo == "20251097616-SEMSUR"
        assert item.record_id == 2292
        assert item.modalidade == "Pregão Eletrônico"
        assert item.modalidade_slug == "pregao-eletronico"
        assert item.tipo_licitacao == "Menor Preco"
        assert "Administracao" in item.orgao
        assert item.data_publicacao == "24/02/2026"
        assert "ferramentas" in item.objeto

    def test_second_item(self):
        items = parse_listing_page(LISTING_HTML, "pregao-eletronico", "Pregão Eletrônico")
        assert items[1].numero_licitacao == "91.012/2026"
        assert items[1].record_id == 2290

    def test_empty_html(self):
        items = parse_listing_page("<html><body></body></html>", "pregao-eletronico", "Pregão Eletrônico")
        assert len(items) == 0


class TestParseTotalPages:
    def test_extracts_pages(self):
        total = parse_total_pages(LISTING_HTML)
        assert total == 3

    def test_single_page(self):
        html = "<html><body><table><tr><td>data</td></tr></table></body></html>"
        assert parse_total_pages(html) == 1


class TestParseDetailPage:
    def test_parses_main_fields(self):
        base = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            record_id=2292,
        )
        result = parse_detail_page(DETAIL_HTML, base)
        assert result.titulo == "Aquisição de ferramentas."
        assert "Administração" in result.orgao
        assert "ferramentas" in result.objeto
        assert result.data_abertura == "09/03/2026"
        assert result.local_abertura == "www.gov.br/compras/pt-br"
        assert result.registro_preco == "Sim"
        assert result.tem_detalhe is True

    def test_parses_documentos(self):
        base = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico", record_id=2292)
        result = parse_detail_page(DETAIL_HTML, base)
        assert len(result.documentos) == 1
        assert "EDITAL" in result.documentos[0].nome
        assert "anexo_num_4450.pdf" in result.documentos[0].url

    def test_parses_historico(self):
        base = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico", record_id=2292)
        result = parse_detail_page(DETAIL_HTML, base)
        assert len(result.historico) == 1
        assert result.historico[0].fase == "Publicação"
        assert result.historico[0].data == "24/02/2026"
        assert "fase_num_2246.pdf" in result.historico[0].arquivo_url

    def test_derives_status_from_historico(self):
        base = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico", record_id=2292)
        result = parse_detail_page(DETAIL_HTML, base)
        assert result.status == "Publicação"

    def test_parses_licitantes(self):
        base = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico", record_id=2292)
        result = parse_detail_page(DETAIL_HTML, base)
        assert len(result.licitantes) == 2
        assert result.licitantes[0].nome == "EMPRESA XYZ LTDA"
        assert result.licitantes[0].situacao == "Habilitada"
        assert result.licitantes[1].situacao == "Desclassificada"


# ── Model Tests ──────────────────────────────────


class TestLicitacaoNatal:
    def test_hash_registro(self):
        lic = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico")
        assert len(lic.hash_registro) == 32  # MD5

    def test_hash_changes_with_data(self):
        lic1 = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico", objeto="A")
        lic2 = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico", objeto="B")
        assert lic1.hash_registro != lic2.hash_registro

    def test_default_metadata(self):
        lic = LicitacaoNatal(numero_licitacao="91.004/2026", modalidade_slug="pregao-eletronico")
        assert lic.fonte == "central_compras_natal"
        assert lic.uf == "RN"
        assert lic.municipio == "Natal"


# ── Storage Tests ────────────────────────────────


class TestStorage:
    def test_upsert_new(self, tmp_db):
        lic = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            objeto="Ferramentas",
        )
        assert tmp_db.upsert(lic) is True
        assert tmp_db.count()["total"] == 1

    def test_upsert_no_change(self, tmp_db):
        lic = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            objeto="Ferramentas",
        )
        tmp_db.upsert(lic)
        assert tmp_db.upsert(lic) is False  # No change

    def test_upsert_update(self, tmp_db):
        lic1 = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            objeto="V1",
        )
        tmp_db.upsert(lic1)

        lic2 = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            objeto="V2",
        )
        assert tmp_db.upsert(lic2) is True

    def test_preserves_detail(self, tmp_db):
        detailed = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            objeto="Ferramentas",
            tem_detalhe=True,
        )
        tmp_db.upsert(detailed)

        listing_only = LicitacaoNatal(
            numero_licitacao="91.004/2026",
            modalidade_slug="pregao-eletronico",
            objeto="Ferramentas",
            tem_detalhe=False,
        )
        tmp_db.upsert(listing_only)

        # Detail should be preserved
        counts = tmp_db.count()
        assert counts["com_detalhe"] == 1

    def test_batch_upsert(self, tmp_db):
        items = [
            LicitacaoNatal(numero_licitacao="91.001/2026", modalidade_slug="pregao-eletronico", objeto="A"),
            LicitacaoNatal(numero_licitacao="91.002/2026", modalidade_slug="pregao-eletronico", objeto="B"),
            LicitacaoNatal(numero_licitacao="91.003/2026", modalidade_slug="pregao-eletronico", objeto="C"),
        ]
        inserted, updated = tmp_db.upsert_batch(items)
        assert inserted == 3
        assert updated == 0
        assert tmp_db.count()["total"] == 3

    def test_get_without_detail(self, tmp_db):
        tmp_db.upsert(LicitacaoNatal(
            numero_licitacao="91.001/2026",
            modalidade_slug="pregao-eletronico",
            record_id=1,
            tem_detalhe=False,
        ))
        tmp_db.upsert(LicitacaoNatal(
            numero_licitacao="91.002/2026",
            modalidade_slug="pregao-eletronico",
            record_id=2,
            tem_detalhe=True,
        ))
        pending = tmp_db.get_without_detail()
        assert len(pending) == 1
        assert pending[0]["numero_licitacao"] == "91.001/2026"

    def test_search(self, tmp_db):
        tmp_db.upsert(LicitacaoNatal(
            numero_licitacao="91.001/2026",
            modalidade_slug="pregao-eletronico",
            objeto="Fornecimento de ferramentas",
        ))
        results = tmp_db.search("ferramentas")
        assert len(results) == 1

    def test_stats_by_modalidade(self, tmp_db):
        tmp_db.upsert(LicitacaoNatal(numero_licitacao="1", modalidade_slug="pregao-eletronico", modalidade="Pregão Eletrônico"))
        tmp_db.upsert(LicitacaoNatal(numero_licitacao="2", modalidade_slug="pregao-eletronico", modalidade="Pregão Eletrônico"))
        tmp_db.upsert(LicitacaoNatal(numero_licitacao="3", modalidade_slug="dispensa-licitacao", modalidade="Dispensa"))
        stats = tmp_db.stats_by_modalidade()
        assert len(stats) == 2
        assert stats[0]["total"] == 2  # pregao has more


# ── Config Tests ─────────────────────────────────


class TestConfig:
    def test_modalidades(self):
        assert len(MODALIDADES) == 7
        assert "pregao-eletronico" in MODALIDADES

    def test_urls(self):
        s = Settings()
        assert "natal.rn.gov.br" in s.base_url
        assert s.detail_url("pregao-eletronico", 2292) == (
            "https://centraldecompras.natal.rn.gov.br/paginas/licitacoes/consulta/?mod=pregao-eletronico&id=2292"
        )
