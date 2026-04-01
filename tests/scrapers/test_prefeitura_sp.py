"""Testes para o scraper da Prefeitura de SP (via PNCP)."""

import tempfile
from pathlib import Path

import pytest

from scrapers.prefeitura_sp.config import Settings, MODALIDADES, IBGE_SAO_PAULO
from scrapers.prefeitura_sp.models import LicitacaoSP, OrgaoSP, parse_api_item
from scrapers.prefeitura_sp.storage import Storage


# ── Fixtures ─────────────────────────────────────


API_ITEM_MUNICIPAL = {
    "numeroControlePNCP": "46395000000139-1-000001/2026",
    "numeroCompra": "000001/2026",
    "sequencialCompra": 1,
    "processo": "6017.2025/0001234-5",
    "anoCompra": 2026,
    "orgaoEntidade": {
        "cnpj": "46395000000139",
        "razaoSocial": "PREFEITURA MUNICIPAL DE SAO PAULO",
        "esferaId": "M",
        "poderId": "E",
    },
    "unidadeOrgao": {
        "nomeUnidade": "Secretaria Municipal de Educação",
        "codigoUnidade": "123456",
    },
    "modalidadeId": 6,
    "modalidadeNome": "Pregão - Eletrônico",
    "modoDisputaId": 1,
    "modoDisputaNome": "Aberto",
    "tipoInstrumentoConvocatorioNome": "Edital",
    "amparoLegal": {"nome": "Lei 14.133/2021, Art. 28, I"},
    "objetoCompra": "Aquisição de material escolar para rede municipal",
    "valorTotalEstimado": 1500000.00,
    "valorTotalHomologado": None,
    "informacaoComplementar": "Lote único",
    "dataPublicacaoPncp": "2026-03-01T10:00:00",
    "dataAberturaProposta": "2026-03-15T09:00:00",
    "dataEncerramentoProposta": "2026-03-15T18:00:00",
    "situacaoCompraId": 1,
    "situacaoCompraNome": "Divulgada",
    "srp": True,
    "linkSistemaOrigem": "https://compras.prefeitura.sp.gov.br/edital/123",
    "linkProcessoEletronico": "",
}

API_ITEM_ESTADUAL = {
    "numeroControlePNCP": "00000000000191-1-000099/2026",
    "orgaoEntidade": {
        "cnpj": "00000000000191",
        "razaoSocial": "GOVERNO DO ESTADO DE SP",
        "esferaId": "E",
        "poderId": "E",
    },
    "unidadeOrgao": {"nomeUnidade": "Secretaria Estadual", "codigoUnidade": "999"},
    "modalidadeId": 6,
    "modalidadeNome": "Pregão - Eletrônico",
    "objetoCompra": "Serviço estadual qualquer",
    "situacaoCompraNome": "Divulgada",
}

API_ITEM_MINIMAL = {
    "numeroControlePNCP": "46395000000139-1-000002/2026",
    "orgaoEntidade": {"esferaId": "M"},
    "unidadeOrgao": {},
    "modalidadeId": 8,
    "objetoCompra": "Dispensa simples",
}


@pytest.fixture
def tmp_db():
    with tempfile.TemporaryDirectory() as d:
        db = Storage(Path(d) / "test.db")
        yield db
        db.close()


def _make_licitacao(**overrides) -> LicitacaoSP:
    defaults = {
        "numero_controle_pncp": "46395000000139-1-000001/2026",
        "objeto": "Material escolar",
        "modalidade_id": 6,
        "modalidade": "Pregão - Eletrônico",
    }
    defaults.update(overrides)
    return LicitacaoSP(**defaults)


# ── Parser Tests ─────────────────────────────────


class TestParseApiItem:
    def test_parses_municipal(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert result is not None
        assert result.numero_controle_pncp == "46395000000139-1-000001/2026"
        assert result.numero_compra == "000001/2026"
        assert result.numero_processo == "6017.2025/0001234-5"
        assert result.ano_compra == 2026

    def test_orgao_fields(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert result.orgao.cnpj == "46395000000139"
        assert "PREFEITURA" in result.orgao.razao_social
        assert result.orgao.esfera == "M"
        assert result.orgao.unidade_nome == "Secretaria Municipal de Educação"

    def test_modalidade(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert result.modalidade_id == 6
        assert result.modalidade == "Pregão - Eletrônico"
        assert result.modo_disputa == "Aberto"

    def test_objeto_e_valores(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert "material escolar" in result.objeto.lower()
        assert result.valor_estimado == 1500000.00
        assert result.valor_homologado is None

    def test_datas(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert result.data_publicacao == "2026-03-01T10:00:00"
        assert result.data_abertura == "2026-03-15T09:00:00"
        assert result.data_encerramento == "2026-03-15T18:00:00"

    def test_situacao_e_srp(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert result.situacao == "Divulgada"
        assert result.srp is True

    def test_link_sistema(self):
        result = parse_api_item(API_ITEM_MUNICIPAL)
        assert "compras.prefeitura.sp.gov.br" in result.link_sistema_origem

    def test_filtra_estadual(self):
        result = parse_api_item(API_ITEM_ESTADUAL)
        assert result is None

    def test_minimal_item(self):
        result = parse_api_item(API_ITEM_MINIMAL)
        assert result is not None
        assert result.modalidade_id == 8
        assert result.objeto == "Dispensa simples"
        assert result.orgao.cnpj == ""

    def test_empty_dict(self):
        result = parse_api_item({})
        assert result is None  # No esferaId → not "M"


# ── Model Tests ──────────────────────────────────


class TestLicitacaoSP:
    def test_hash_registro(self):
        lic = _make_licitacao()
        assert len(lic.hash_registro) == 32  # MD5

    def test_hash_changes_with_objeto(self):
        lic1 = _make_licitacao(objeto="A")
        lic2 = _make_licitacao(objeto="B")
        assert lic1.hash_registro != lic2.hash_registro

    def test_hash_changes_with_situacao(self):
        lic1 = _make_licitacao(situacao="Divulgada")
        lic2 = _make_licitacao(situacao="Encerrada")
        assert lic1.hash_registro != lic2.hash_registro

    def test_hash_same_data(self):
        lic1 = _make_licitacao()
        lic2 = _make_licitacao()
        assert lic1.hash_registro == lic2.hash_registro

    def test_url_pncp(self):
        lic = _make_licitacao()
        assert lic.url_pncp == "https://pncp.gov.br/app/editais/46395000000139-1-000001/2026"

    def test_url_pncp_empty(self):
        lic = _make_licitacao(numero_controle_pncp="")
        assert lic.url_pncp == ""

    def test_default_metadata(self):
        lic = _make_licitacao()
        assert lic.fonte == "PNCP-PMSP"
        assert lic.uf == "SP"
        assert lic.municipio == "São Paulo"


# ── Storage Tests ────────────────────────────────


class TestStorage:
    def test_upsert_new(self, tmp_db):
        lic = _make_licitacao()
        assert tmp_db.upsert(lic) is True
        assert tmp_db.count()["total"] == 1

    def test_upsert_no_change(self, tmp_db):
        lic = _make_licitacao()
        tmp_db.upsert(lic)
        assert tmp_db.upsert(lic) is False

    def test_upsert_update(self, tmp_db):
        tmp_db.upsert(_make_licitacao(objeto="V1"))
        assert tmp_db.upsert(_make_licitacao(objeto="V2")) is True
        assert tmp_db.count()["total"] == 1

    def test_batch_upsert(self, tmp_db):
        items = [
            _make_licitacao(numero_controle_pncp="A-001", objeto="Item A"),
            _make_licitacao(numero_controle_pncp="A-002", objeto="Item B"),
            _make_licitacao(numero_controle_pncp="A-003", objeto="Item C"),
        ]
        inserted, updated = tmp_db.upsert_batch(items)
        assert inserted == 3
        assert updated == 0
        assert tmp_db.count()["total"] == 3

    def test_batch_upsert_with_updates(self, tmp_db):
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="A-001", objeto="Old"))
        items = [
            _make_licitacao(numero_controle_pncp="A-001", objeto="New"),
            _make_licitacao(numero_controle_pncp="A-002", objeto="Brand new"),
        ]
        inserted, updated = tmp_db.upsert_batch(items)
        assert inserted == 1
        assert updated == 1

    def test_search_by_objeto(self, tmp_db):
        tmp_db.upsert(_make_licitacao(objeto="Aquisição de material escolar"))
        results = tmp_db.search("material escolar")
        assert len(results) == 1

    def test_search_by_orgao(self, tmp_db):
        lic = _make_licitacao()
        lic.orgao = OrgaoSP(razao_social="PREFEITURA MUNICIPAL DE SAO PAULO")
        tmp_db.upsert(lic)
        results = tmp_db.search("PREFEITURA")
        assert len(results) == 1

    def test_search_no_results(self, tmp_db):
        tmp_db.upsert(_make_licitacao())
        results = tmp_db.search("inexistente_xyz")
        assert len(results) == 0

    def test_stats_by_modalidade(self, tmp_db):
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="A", modalidade_id=6, modalidade="Pregão"))
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="B", modalidade_id=6, modalidade="Pregão"))
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="C", modalidade_id=8, modalidade="Dispensa"))
        stats = tmp_db.stats_by_modalidade()
        assert len(stats) == 2
        assert stats[0]["total"] == 2  # Pregão

    def test_stats_by_orgao(self, tmp_db):
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="A"))
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="B"))
        stats = tmp_db.stats_by_orgao()
        assert len(stats) >= 1

    def test_stats_by_situacao(self, tmp_db):
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="A", situacao="Divulgada"))
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="B", situacao="Encerrada"))
        stats = tmp_db.stats_by_situacao()
        assert len(stats) == 2

    def test_export_all(self, tmp_db):
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="A"))
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="B"))
        data = tmp_db.export_all()
        assert len(data) == 2

    def test_count_by_modalidade(self, tmp_db):
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="A", modalidade_id=6))
        tmp_db.upsert(_make_licitacao(numero_controle_pncp="B", modalidade_id=8))
        assert tmp_db.count(modalidade_id=6)["total"] == 1
        assert tmp_db.count(modalidade_id=8)["total"] == 1
        assert tmp_db.count()["total"] == 2


# ── Config Tests ─────────────────────────────────


class TestConfig:
    def test_modalidades_count(self):
        assert len(MODALIDADES) == 13

    def test_modalidades_keys(self):
        assert 1 in MODALIDADES  # Leilão
        assert 6 in MODALIDADES  # Pregão Eletrônico
        assert 13 in MODALIDADES  # Leilão Eletrônico

    def test_ibge_code(self):
        assert IBGE_SAO_PAULO == "3550308"

    def test_settings_defaults(self):
        s = Settings()
        assert s.uf == "SP"
        assert s.ibge_municipio == "3550308"
        assert s.page_size == 50

    def test_api_url(self):
        s = Settings()
        assert s.api_url == "https://pncp.gov.br/api/consulta/v1/contratacoes/publicacao"
