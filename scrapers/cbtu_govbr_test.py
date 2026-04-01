"""Testes para o scraper CBTU gov.br.

Valida que o scraper consegue extrair pelo menos 1 licitação real
do portal gov.br/cbtu e que os dados estão bem formados.
"""

import tempfile
from pathlib import Path

import pytest

from scrapers.cbtu_govbr import CBTUGovBRScraper
from scrapers.models.cbtu import (
    DocumentoCBTU,
    LicitacaoCBTU,
    classify_document,
    infer_status,
)


# ── Model tests ──────────────────────────────────────


class TestDocumentClassification:
    def test_edital(self):
        assert classify_document("00 Edital - Serviços.pdf") == "edital"

    def test_termo_referencia(self):
        assert classify_document("01 TR-Outsourcing PEL.pdf") == "termo_referencia"
        assert classify_document("Termo de Referência v2.pdf") == "termo_referencia"

    def test_julgamento(self):
        assert classify_document("Termo de Julgamento PE 03.pdf") == "julgamento"
        assert classify_document("Resultado final.pdf") == "julgamento"

    def test_homologacao(self):
        assert classify_document("Homologação PEL 90001.pdf") == "homologacao"

    def test_recurso(self):
        assert classify_document("03 CBTU RECURSO - SOLUÇÕES.pdf") == "recurso"
        assert classify_document("Impugnação ao Edital.pdf") == "recurso"
        assert classify_document("09 Contrarrazoes.pdf") == "recurso"

    def test_aviso(self):
        assert classify_document("Aviso de Publicação no DOU.pdf") == "aviso"

    def test_decisao(self):
        assert classify_document("06 DECISÃO PREGOEIRO.pdf") == "decisao"

    def test_outros(self):
        assert classify_document("arquivo_generico.pdf") == "outros"


class TestStatusInference:
    def test_homologada(self):
        docs = [
            DocumentoCBTU(nome="Edital.pdf", url="x", tipo="edital"),
            DocumentoCBTU(nome="Julgamento.pdf", url="x", tipo="julgamento"),
            DocumentoCBTU(nome="Homologação.pdf", url="x", tipo="homologacao"),
        ]
        assert infer_status(docs) == "homologada"

    def test_com_recurso(self):
        docs = [
            DocumentoCBTU(nome="Edital.pdf", url="x", tipo="edital"),
            DocumentoCBTU(nome="Recurso.pdf", url="x", tipo="recurso"),
        ]
        assert infer_status(docs) == "com_recurso"

    def test_em_julgamento(self):
        docs = [
            DocumentoCBTU(nome="Edital.pdf", url="x", tipo="edital"),
            DocumentoCBTU(nome="Julgamento.pdf", url="x", tipo="julgamento"),
        ]
        assert infer_status(docs) == "em_julgamento"

    def test_publicada(self):
        docs = [DocumentoCBTU(nome="Edital.pdf", url="x", tipo="edital")]
        assert infer_status(docs) == "publicada"

    def test_desconhecido(self):
        docs = [DocumentoCBTU(nome="arquivo.pdf", url="x", tipo="outros")]
        assert infer_status(docs) == "desconhecido"


class TestLicitacaoModel:
    def test_hash_registro(self):
        lic = LicitacaoCBTU(
            numero_processo="90027/2025",
            modalidade="Pregão Eletrônico",
            titulo="Outsourcing de impressão",
            unidade_slug="cbtu-recife",
            unidade_nome="STU Recife",
            url_processo="https://example.com/process",
        )
        assert len(lic.hash_registro) == 16
        # Hash deve ser determinístico
        assert lic.hash_registro == lic.hash_registro

    def test_hash_changes_with_status(self):
        base = dict(
            numero_processo="90027/2025",
            modalidade="Pregão Eletrônico",
            titulo="Outsourcing de impressão",
            unidade_slug="cbtu-recife",
            unidade_nome="STU Recife",
            url_processo="https://example.com/process",
        )
        lic1 = LicitacaoCBTU(**base, status="publicada")
        lic2 = LicitacaoCBTU(**base, status="homologada")
        assert lic1.hash_registro != lic2.hash_registro


# ── Scraper parsing tests ────────────────────────────


class TestScraperParsing:
    def setup_method(self):
        self.scraper = CBTUGovBRScraper()

    def test_extract_numero_processo(self):
        assert self.scraper._extract_numero_processo("PREGÃO 90027/2025") == "90027/2025"
        assert self.scraper._extract_numero_processo("Pregão eletrônico nº 90003/2025") == "90003/2025"
        assert self.scraper._extract_numero_processo("Concorrência 001-2025") == "001-2025"

    def test_detect_modalidade(self):
        url = "https://www.gov.br/.../cbtu-recife/pregoes-2025/pregao-90027-2025"
        assert self.scraper._detect_modalidade(url) == "Pregão Eletrônico"

        url2 = "https://www.gov.br/.../administracao-central/concorrencia-lec/concorrencias-2025/conc-001"
        assert self.scraper._detect_modalidade(url2) == "Concorrência"

    def test_is_document_link(self):
        assert self.scraper._is_document_link("https://example.com/file.pdf/view")
        assert self.scraper._is_document_link("https://example.com/file.zip")
        assert not self.scraper._is_document_link("https://example.com/folder/subfolder")

    def test_extract_valor(self):
        assert self.scraper._extract_valor("Valor estimado: R$ 1.500.000,00") == 1500000.0
        assert self.scraper._extract_valor("Sem valor definido") is None

    def test_unidades(self):
        assert len(self.scraper.UNIDADES) == 5
        assert "cbtu-recife" in self.scraper.UNIDADES


# ── Storage tests ────────────────────────────────────


class TestStorage:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = Path(self.tmpdir) / "test.db"
        self.scraper = CBTUGovBRScraper(db_path=self.db_path)

    def test_save_and_stats(self):
        lics = [
            LicitacaoCBTU(
                numero_processo="90001/2025",
                modalidade="Pregão Eletrônico",
                titulo="Teste 1",
                unidade_slug="cbtu-recife",
                unidade_nome="STU Recife",
                url_processo="https://example.com/1",
                status="publicada",
                documentos=[
                    DocumentoCBTU(nome="edital.pdf", url="https://x/e.pdf", tipo="edital"),
                ],
            ),
            LicitacaoCBTU(
                numero_processo="90002/2025",
                modalidade="Pregão Eletrônico",
                titulo="Teste 2",
                unidade_slug="cbtu-recife",
                unidade_nome="STU Recife",
                url_processo="https://example.com/2",
                status="homologada",
            ),
        ]
        new, updated, unchanged = self.scraper.save(lics)
        assert new == 2
        assert updated == 0

        stats = self.scraper.stats()
        assert stats["total"] == 2
        assert stats["documentos"] == 1
        assert stats["by_unidade"]["STU Recife"] == 2

    def test_upsert_detects_changes(self):
        lic = LicitacaoCBTU(
            numero_processo="90001/2025",
            modalidade="Pregão Eletrônico",
            titulo="Teste",
            unidade_slug="cbtu-recife",
            unidade_nome="STU Recife",
            url_processo="https://example.com/1",
            status="publicada",
        )
        new, _, _ = self.scraper.save([lic])
        assert new == 1

        # Mesma licitação sem mudança
        _, _, unchanged = self.scraper.save([lic])
        assert unchanged == 1

        # Com mudança de status
        lic.status = "homologada"
        _, updated, _ = self.scraper.save([lic])
        assert updated == 1

    def test_search(self):
        lic = LicitacaoCBTU(
            numero_processo="90027/2025",
            modalidade="Pregão Eletrônico",
            titulo="Outsourcing de impressão",
            unidade_slug="cbtu-recife",
            unidade_nome="STU Recife",
            url_processo="https://example.com/1",
        )
        self.scraper.save([lic])
        results = self.scraper.search("impressão")
        assert len(results) == 1
        assert results[0]["numero_processo"] == "90027/2025"


# ── Integration test (real data) ─────────────────────


@pytest.mark.asyncio
async def test_scrape_real_data():
    """Testa scraping real de pelo menos 1 licitação do portal CBTU."""
    scraper = CBTUGovBRScraper()
    async with scraper:
        results = await scraper.scrape(unidades=["cbtu-recife"], max_items=3)

    assert len(results) >= 1, "Deve retornar pelo menos 1 licitação"

    lic = results[0]
    assert lic.numero_processo, "Deve ter número do processo"
    assert lic.modalidade, "Deve ter modalidade"
    assert lic.titulo, "Deve ter título"
    assert lic.unidade_slug == "cbtu-recife"
    assert lic.unidade_nome == "STU Recife"
    assert lic.url_processo.startswith("https://www.gov.br/cbtu/")
    assert lic.fonte == "CBTU-GOVBR"
    assert len(lic.documentos) > 0, "Deve ter pelo menos 1 documento"
