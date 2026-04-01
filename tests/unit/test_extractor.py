"""Testes para o EditalExtractor."""

import pytest
from datetime import datetime
from decimal import Decimal

from licitabrasil.processors.extractor import (
    EditalExtractor,
    SecaoEdital,
)


@pytest.fixture
def extractor():
    return EditalExtractor()


class TestParseValor:
    """Testes para extração de valores monetários."""

    def test_valor_simples(self, extractor):
        valor = extractor._parse_primeiro_valor("R$ 1.234.567,89")
        assert valor == Decimal("1234567.89")

    def test_valor_sem_centavos(self, extractor):
        valor = extractor._parse_primeiro_valor("R$ 50.000")
        assert valor == Decimal("50000")

    def test_valor_com_espaco(self, extractor):
        valor = extractor._parse_primeiro_valor("R$  150.000,00 para a contratação")
        assert valor == Decimal("150000.00")

    def test_valor_nenhum(self, extractor):
        valor = extractor._parse_primeiro_valor("sem valor definido")
        assert valor is None

    def test_valor_grande(self, extractor):
        valor = extractor._parse_primeiro_valor("R$ 12.345.678,90")
        assert valor == Decimal("12345678.90")

    def test_valor_pequeno(self, extractor):
        valor = extractor._parse_primeiro_valor("R$ 500,00")
        assert valor == Decimal("500.00")


class TestParseData:
    """Testes para extração de datas BR."""

    def test_data_completa(self, extractor):
        dt = extractor._parse_primeira_data("abertura em 15/03/2025 às 10h30")
        assert dt == datetime(2025, 3, 15, 10, 30)

    def test_data_sem_hora(self, extractor):
        dt = extractor._parse_primeira_data("data: 01/12/2024")
        assert dt == datetime(2024, 12, 1, 0, 0)

    def test_data_ano_curto(self, extractor):
        dt = extractor._parse_primeira_data("25/06/25")
        assert dt == datetime(2025, 6, 25, 0, 0)

    def test_data_hora_com_dois_pontos(self, extractor):
        dt = extractor._parse_primeira_data("10/05/2025 14:00")
        assert dt == datetime(2025, 5, 10, 14, 0)

    def test_sem_data(self, extractor):
        dt = extractor._parse_primeira_data("sem data definida")
        assert dt is None

    def test_data_invalida(self, extractor):
        dt = extractor._parse_primeira_data("32/13/2025")
        assert dt is None


class TestDetecaoMeEpp:
    """Testes para detecção de exclusividade ME/EPP."""

    def test_exclusiva_me_epp(self, extractor):
        texto = "Esta licitação é exclusiva para ME/EPP conforme LC 123/2006"
        assert extractor._detectar_me_epp(texto) is True

    def test_reservada_microempresa(self, extractor):
        texto = "Participação reservada às microempresas e empresas de pequeno porte"
        assert extractor._detectar_me_epp(texto) is True

    def test_nao_exclusiva(self, extractor):
        texto = "Aberto a qualquer empresa que cumpra os requisitos do edital"
        assert extractor._detectar_me_epp(texto) is False


class TestCriterioJulgamento:
    """Testes para extração de critério de julgamento."""

    def test_menor_preco(self, extractor):
        secoes = [SecaoEdital(tipo="JULGAMENTO", texto="O critério de julgamento será menor preço global", pagina_inicio=1, pagina_fim=1, confianca=0.8)]
        resultado = extractor._extrair_criterio_julgamento(secoes, "")
        assert resultado == "menor preço"

    def test_tecnica_e_preco(self, extractor):
        resultado = extractor._extrair_criterio_julgamento([], "O tipo será técnica e preço para este certame")
        assert resultado == "técnica e preço"

    def test_maior_desconto(self, extractor):
        resultado = extractor._extrair_criterio_julgamento([], "Critério: maior desconto sobre tabela")
        assert resultado == "maior desconto"


class TestIdentificarSecoes:
    """Testes para identificação de seções do edital."""

    def test_secao_objeto(self, extractor):
        pages = ["PREGÃO ELETRÔNICO\n\n1. DO OBJETO\nContratação de serviços de limpeza e conservação."]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "OBJETO" for s in secoes)

    def test_secao_habilitacao(self, extractor):
        pages = ["5. DA HABILITAÇÃO\n5.1 Para habilitação devem ser apresentados os seguintes documentos:"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "HABILITACAO" for s in secoes)

    def test_secao_valor(self, extractor):
        pages = ["3. DO VALOR ESTIMADO\nO valor estimado para a contratação é de R$ 500.000,00"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "VALOR" for s in secoes)

    def test_multiplas_secoes(self, extractor):
        pages = [
            "1. DO OBJETO\nContratação de serviços.\n\n"
            "2. DO VALOR ESTIMADO\nR$ 100.000,00\n\n"
            "3. DA HABILITAÇÃO\nDocumentos necessários."
        ]
        secoes = extractor._identificar_secoes(pages)
        tipos = {s.tipo for s in secoes}
        assert "OBJETO" in tipos
        assert "VALOR" in tipos
        assert "HABILITACAO" in tipos


class TestExtrairRequisitosHabilitacao:
    """Testes para extração de requisitos."""

    def test_requisitos_com_alineas(self, extractor):
        secoes = [SecaoEdital(
            tipo="HABILITACAO",
            texto="a) Certidão negativa de débitos\nb) Atestado de capacidade técnica\nc) Balanço patrimonial",
            pagina_inicio=5, pagina_fim=5, confianca=0.8,
        )]
        reqs = extractor._extrair_requisitos_habilitacao(secoes)
        assert len(reqs) == 3
        assert "Certidão" in reqs[0]

    def test_requisitos_por_keywords(self, extractor):
        secoes = [SecaoEdital(
            tipo="HABILITACAO",
            texto="Apresentar Certidão negativa federal\nAlvará de funcionamento\nRegistro no CREA",
            pagina_inicio=5, pagina_fim=5, confianca=0.8,
        )]
        reqs = extractor._extrair_requisitos_habilitacao(secoes)
        assert len(reqs) >= 2


class TestCotaReservada:
    """Testes para detecção de cota reservada."""

    def test_cota_reservada_detectada(self, extractor):
        texto = "Será adotada cota de 25% reservada para ME/EPP conforme Art. 48"
        assert extractor._detectar_cota_reservada(texto) is True

    def test_cota_reservada_percentual(self, extractor):
        texto = "cota reservada de participação exclusiva"
        assert extractor._detectar_cota_reservada(texto) is True

    def test_sem_cota_reservada(self, extractor):
        texto = "Abertura ampla para todas as empresas"
        assert extractor._detectar_cota_reservada(texto) is False


class TestMargemPreferencia:
    """Testes para detecção de margem de preferência."""

    def test_margem_detectada(self, extractor):
        texto = "Será aplicada margem de preferência de 25% para produtos nacionais"
        assert extractor._detectar_margem_preferencia(texto) is True

    def test_sem_margem(self, extractor):
        texto = "Não haverá tratamento diferenciado"
        assert extractor._detectar_margem_preferencia(texto) is False


class TestGarantia:
    """Testes para extração de garantia contratual."""

    def test_garantia_com_percentual(self, extractor):
        secoes = [SecaoEdital(
            tipo="GARANTIA",
            texto="A contratada deverá prestar garantia contratual de 5% do valor do contrato",
            pagina_inicio=10, pagina_fim=10, confianca=0.8,
        )]
        g = extractor._extrair_garantia(secoes, "")
        assert g.exige is True
        assert g.percentual == 5.0

    def test_garantia_sem_secao(self, extractor):
        texto = "Será exigida garantia de execução contratual no percentual de 3% do valor global"
        g = extractor._extrair_garantia([], texto)
        assert g.exige is True
        assert g.percentual == 3.0

    def test_sem_garantia(self, extractor):
        g = extractor._extrair_garantia([], "Nenhuma menção a garantia neste edital")
        assert g.exige is False
        assert g.percentual is None


class TestSubcontratacao:
    """Testes para detecção de subcontratação."""

    def test_subcontratacao_permitida(self, extractor):
        texto = "É permitida a subcontratação parcial do objeto"
        assert extractor._detectar_subcontratacao([], texto) is True

    def test_subcontratacao_vedada(self, extractor):
        texto = "É vedada a subcontratação total ou parcial"
        assert extractor._detectar_subcontratacao([], texto) is False

    def test_subcontratacao_nao_mencionada(self, extractor):
        texto = "Contratação de serviços de limpeza"
        assert extractor._detectar_subcontratacao([], texto) is None

    def test_subcontratacao_admitida(self, extractor):
        texto = "A subcontratação será admitida até o limite de 30%"
        assert extractor._detectar_subcontratacao([], texto) is True


class TestConsorcio:
    """Testes para detecção de consórcio."""

    def test_consorcio_vedado(self, extractor):
        texto = "Não será permitida a participação de consórcio"
        assert extractor._detectar_consorcio([], texto) is False

    def test_consorcio_permitido(self, extractor):
        texto = "É admitida a participação em consórcio"
        assert extractor._detectar_consorcio([], texto) is True

    def test_consorcio_nao_mencionado(self, extractor):
        texto = "Pregão eletrônico para aquisição de material"
        assert extractor._detectar_consorcio([], texto) is None

    def test_consorcio_proibido_variante(self, extractor):
        texto = "O consórcio não será admitido nesta licitação"
        assert extractor._detectar_consorcio([], texto) is False


class TestVisitaTecnica:
    """Testes para detecção de visita técnica."""

    def test_visita_obrigatoria(self, extractor):
        texto = "A visita técnica é obrigatória e deverá ser agendada"
        assert extractor._detectar_visita_tecnica([], texto) == "obrigatoria"

    def test_visita_facultativa(self, extractor):
        texto = "A visita técnica será facultativa"
        assert extractor._detectar_visita_tecnica([], texto) == "facultativa"

    def test_sem_visita(self, extractor):
        texto = "Não há menção a visitas neste edital"
        assert extractor._detectar_visita_tecnica([], texto) is None


class TestAmostra:
    """Testes para detecção de exigência de amostra."""

    def test_amostra_exigida(self, extractor):
        texto = "Será exigida a apresentação de amostra para avaliação"
        assert extractor._detectar_amostra([], texto) is True

    def test_sem_amostra(self, extractor):
        texto = "Os produtos devem atender à norma ABNT 12345"
        assert extractor._detectar_amostra([], texto) is False


class TestPenalidades:
    """Testes para extração de penalidades."""

    def test_penalidades_com_multa(self, extractor):
        secoes = [SecaoEdital(
            tipo="PENALIDADES",
            texto=(
                "I - Advertência para infrações leves\n"
                "II - Multa de 10% sobre o valor do contrato\n"
                "III - Suspensão temporária de licitar por 2 anos\n"
                "IV - Item sem keyword relevante"
            ),
            pagina_inicio=15, pagina_fim=15, confianca=0.8,
        )]
        pens = extractor._extrair_penalidades(secoes)
        assert len(pens) == 3
        assert any("multa" in p.lower() for p in pens)
        assert any("suspensão" in p.lower() for p in pens)

    def test_sem_penalidades(self, extractor):
        assert extractor._extrair_penalidades([]) == []


class TestCategorizarHabilitacao:
    """Testes para categorização de habilitação."""

    def test_categoriza_documentos(self, extractor):
        secoes = [SecaoEdital(
            tipo="HABILITACAO",
            texto=(
                "a) Contrato social registrado na Junta Comercial\n"
                "b) Certidão negativa de débitos federais\n"
                "c) Atestado de capacidade técnica operacional\n"
                "d) Balanço patrimonial do último exercício"
            ),
            pagina_inicio=5, pagina_fim=5, confianca=0.8,
        )]
        hab = extractor._categorizar_habilitacao(secoes, "")
        assert len(hab.juridica) >= 1
        assert len(hab.fiscal) >= 1
        assert len(hab.tecnica) >= 1
        assert len(hab.economico_financeira) >= 1


class TestNovasSecoes:
    """Testes para identificação das novas seções."""

    def test_secao_garantia(self, extractor):
        pages = ["7. DA GARANTIA CONTRATUAL\nA contratada deverá prestar garantia de 5%"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "GARANTIA" for s in secoes)

    def test_secao_subcontratacao(self, extractor):
        pages = ["9. DA SUBCONTRATAÇÃO\nÉ vedada a subcontratação total"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "SUBCONTRATACAO" for s in secoes)

    def test_secao_consorcio(self, extractor):
        pages = ["8. DO CONSÓRCIO\nNão será admitida a participação"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "CONSORCIO" for s in secoes)

    def test_secao_visita(self, extractor):
        pages = ["10. DA VISITA TÉCNICA\nA visita será facultativa"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "VISITA" for s in secoes)

    def test_secao_amostra(self, extractor):
        pages = ["11. DA AMOSTRA\nSerá exigida apresentação de amostra"]
        secoes = extractor._identificar_secoes(pages)
        assert any(s.tipo == "AMOSTRA" for s in secoes)


class TestEditalExtraidoArquivo:
    """Teste de integração com arquivo não existente."""

    def test_arquivo_nao_encontrado(self, extractor):
        with pytest.raises(FileNotFoundError):
            extractor.extrair("/caminho/inexistente.pdf")

    def test_formato_nao_suportado(self, extractor):
        with pytest.raises(ValueError, match="Formato não suportado"):
            extractor.extrair("/caminho/arquivo.txt")
