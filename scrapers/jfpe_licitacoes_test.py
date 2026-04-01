"""Testes para o scraper JFPE.

Valida parsing de dados da API, modelos Pydantic, storage SQLite,
e coleta real de pelo menos 10 licitacoes.
"""

import tempfile
from pathlib import Path

import pytest

from scrapers.jfpe_licitacoes import (
    ArquivoJFPE,
    JFPEScraper,
    LicitacaoJFPE,
    MODALIDADE_MAP,
    extract_modalidade_from_desc,
    extract_objeto,
)


# ── Helper functions ───────────────────────────────────


class TestExtractModalidade:
    def test_pregao_eletronico(self):
        desc = "<span style='color: red'>PREGÃO ELETRÔNICO</span> - Serviços de TI"
        assert extract_modalidade_from_desc(desc) == "Pregão Eletrônico"

    def test_dispensa(self):
        desc = "<span style='color: red'>DISPENSA DE LICITAÇÃO</span> - Manutenção"
        assert extract_modalidade_from_desc(desc) == "Dispensa De Licitação"

    def test_concorrencia(self):
        desc = "CONCORRÊNCIA - Obra de reforma"
        assert extract_modalidade_from_desc(desc) == "Concorrência"

    def test_no_modalidade(self):
        desc = "Serviços gerais de manutenção predial"
        assert extract_modalidade_from_desc(desc) is None


class TestExtractObjeto:
    def test_removes_modalidade_prefix(self):
        desc = "<span>PREGÃO ELETRÔNICO</span> - Serviços de TI para datacenter"
        assert extract_objeto(desc) == "Serviços de TI para datacenter"

    def test_plain_text(self):
        desc = "DISPENSA DE LICITAÇÃO - Manutenção emergencial"
        assert extract_objeto(desc) == "Manutenção emergencial"

    def test_no_prefix(self):
        desc = "Serviços gerais sem prefixo"
        assert extract_objeto(desc) == "Serviços gerais sem prefixo"


# ── Modelos ────────────────────────────────────────────


class TestArquivoModel:
    def test_url_download_edital(self):
        arq = ArquivoJFPE(id_arquivo=1132, nome="edital.pdf", categoria="edital")
        assert "GetLicitacaoFile?idLicitacaoArquivo=1132" in arq.url_download

    def test_url_download_contrato(self):
        arq = ArquivoJFPE(id_arquivo=99, nome="contrato.pdf", categoria="contrato")
        assert "GetContratoFile?idContrato=99" in arq.url_download

    def test_tipo_arquivo_optional(self):
        arq = ArquivoJFPE(id_arquivo=1, nome="file.pdf", tipo_arquivo=None)
        assert arq.tipo_arquivo is None


class TestLicitacaoModel:
    def test_hash_registro(self):
        lic = LicitacaoJFPE(
            id_licitacao=100,
            numero="0001/2025",
            modalidade="Pregão Eletrônico",
            modalidade_codigo=1,
            objeto="Serviços de TI",
        )
        assert len(lic.hash_registro) == 16
        assert lic.hash_registro == lic.hash_registro  # determinisico

    def test_hash_changes_with_qtd(self):
        base = dict(
            id_licitacao=100,
            numero="0001/2025",
            modalidade="Pregão Eletrônico",
            modalidade_codigo=1,
            objeto="Serviços de TI",
        )
        lic1 = LicitacaoJFPE(**base, qtd_contratos=0)
        lic2 = LicitacaoJFPE(**base, qtd_contratos=1)
        assert lic1.hash_registro != lic2.hash_registro

    def test_defaults(self):
        lic = LicitacaoJFPE(
            id_licitacao=1,
            numero="0001/2025",
            modalidade="Pregão",
            modalidade_codigo=1,
            objeto="Teste",
        )
        assert lic.fonte == "JFPE"
        assert lic.e_pregao is False
        assert lic.arquivos == []


class TestModalidadeMap:
    def test_known_codes(self):
        assert MODALIDADE_MAP[1] == "Pregao Eletronico"
        assert MODALIDADE_MAP[5] == "Dispensa de Licitacao"

    def test_all_codes_present(self):
        assert len(MODALIDADE_MAP) >= 6


# ── Scraper parsing ───────────────────────────────────


class TestScraperParsing:
    def setup_method(self):
        self.scraper = JFPEScraper()

    def test_parse_licitacao(self):
        item = {
            "idLicitacao": 1154,
            "data": "02/03/2026",
            "hora": "14:00",
            "numero": "0011/2026",
            "descricao": "<span style='color: red'>DISPENSA DE LICITAÇÃO</span> - Manutenção",
            "quantidadeEmpenhos": 0,
            "quantidadeContratos": 1,
            "quantidadeAtaRegistroPreco": 0,
            "arquivosEdital": [
                {
                    "idArquivo": 1132,
                    "nomeArquivo": "sei_001.pdf",
                    "numeroArquivo": 1,
                    "tipoArquivo": "application/pdf",
                }
            ],
            "modalidadeLicitacao": 5,
            "temRegistroPreco": False,
            "ePregao": False,
            "dataHoraLicitacao": "2026-03-02T14:00:00",
            "numLicitacao": 11,
            "anoLicitacao": 2026,
        }
        lic = self.scraper._parse_licitacao(item)
        assert lic.id_licitacao == 1154
        assert lic.numero == "0011/2026"
        assert "Dispensa" in lic.modalidade
        assert lic.objeto == "Manutenção"
        assert lic.qtd_contratos == 1
        assert len(lic.arquivos) == 1
        assert lic.arquivos[0].nome == "sei_001.pdf"

    def test_parse_licitacao_null_tipo(self):
        item = {
            "idLicitacao": 252,
            "numero": "0052/2010",
            "descricao": "PREGÃO ELETRÔNICO - Teste",
            "quantidadeEmpenhos": 0,
            "quantidadeContratos": 0,
            "quantidadeAtaRegistroPreco": 0,
            "arquivosEdital": [
                {
                    "idArquivo": 99,
                    "nomeArquivo": "arquivo.pdf",
                    "numeroArquivo": 1,
                    "tipoArquivo": None,
                }
            ],
            "modalidadeLicitacao": 1,
            "ePregao": True,
            "dataHoraLicitacao": "2010-08-25T09:00:00",
        }
        lic = self.scraper._parse_licitacao(item)
        assert lic.numero == "0052/2010"
        assert lic.arquivos[0].tipo_arquivo is None

    def test_parse_licitacao_no_files(self):
        item = {
            "idLicitacao": 500,
            "numero": "0001/2020",
            "descricao": "CONVITE - Serviço",
            "quantidadeEmpenhos": 0,
            "quantidadeContratos": 0,
            "quantidadeAtaRegistroPreco": 0,
            "arquivosEdital": [],
            "modalidadeLicitacao": 2,
            "ePregao": False,
        }
        lic = self.scraper._parse_licitacao(item)
        assert len(lic.arquivos) == 0
        assert lic.modalidade_codigo == 2


# ── Storage ────────────────────────────────────────────


class TestStorage:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.scraper = JFPEScraper(db_path=self.db_path)

    def test_save_and_stats(self):
        lics = [
            LicitacaoJFPE(
                id_licitacao=1,
                numero="0001/2025",
                modalidade="Pregão Eletrônico",
                modalidade_codigo=1,
                objeto="Serviços de TI",
                arquivos=[
                    ArquivoJFPE(id_arquivo=10, nome="edital.pdf"),
                ],
            ),
            LicitacaoJFPE(
                id_licitacao=2,
                numero="0002/2025",
                modalidade="Dispensa de Licitação",
                modalidade_codigo=5,
                objeto="Manutenção predial",
            ),
        ]
        new, updated, unchanged = self.scraper.save(lics)
        assert new == 2
        assert updated == 0

        stats = self.scraper.stats()
        assert stats["total"] == 2
        assert stats["arquivos"] == 1

    def test_upsert_detects_changes(self):
        lic = LicitacaoJFPE(
            id_licitacao=1,
            numero="0001/2025",
            modalidade="Pregão",
            modalidade_codigo=1,
            objeto="Teste",
        )
        new, _, _ = self.scraper.save([lic])
        assert new == 1

        # Sem mudanca
        _, _, unchanged = self.scraper.save([lic])
        assert unchanged == 1

        # Com mudanca (novo contrato)
        lic.qtd_contratos = 1
        _, updated, _ = self.scraper.save([lic])
        assert updated == 1

    def test_search(self):
        lic = LicitacaoJFPE(
            id_licitacao=1,
            numero="0001/2025",
            modalidade="Pregão Eletrônico",
            modalidade_codigo=1,
            objeto="Outsourcing de impressão corporativa",
        )
        self.scraper.save([lic])
        results = self.scraper.search("impressão")
        assert len(results) == 1
        assert results[0]["numero"] == "0001/2025"


# ── Integration test (real data) ───────────────────────


@pytest.mark.asyncio
async def test_scrape_real_data():
    """Testa scraping real de pelo menos 10 licitações da API JFPE."""
    scraper = JFPEScraper()
    async with scraper:
        results = await scraper.scrape(max_items=15)

    assert len(results) >= 10, "Deve retornar pelo menos 10 licitações"

    lic = results[0]
    assert lic.id_licitacao > 0
    assert lic.numero, "Deve ter número"
    assert lic.modalidade, "Deve ter modalidade"
    assert lic.objeto, "Deve ter objeto"
    assert lic.fonte == "JFPE"
    assert len(lic.hash_registro) == 16
