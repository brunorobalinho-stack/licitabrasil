"""Testes para o PriceAnalyzer."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from licitabrasil.processors.price_analyzer import (
    FontePreco,
    NivelAlerta,
    PriceAnalyzer,
    RegistroPreco,
    Tendencia,
)


@pytest.fixture
def analyzer():
    return PriceAnalyzer()


def _registro(valor, dias_atras=0, uf=None, fonte=FontePreco.PNCP):
    """Helper para criar RegistroPreco rapidamente."""
    return RegistroPreco(
        descricao_item="Material de limpeza",
        valor_unitario=Decimal(str(valor)),
        data_referencia=datetime(2025, 6, 1) - timedelta(days=dias_atras),
        fonte=fonte,
        uf=uf,
    )


# ---------------------------------------------------------------------------
# Estatísticas básicas
# ---------------------------------------------------------------------------

class TestEstatisticas:
    """Testes para cálculos estatísticos descritivos."""

    def test_media_e_mediana(self, analyzer):
        registros = [_registro(v) for v in [10, 20, 30, 40, 50]]
        result = analyzer.analisar(registros)
        assert result.estatisticas.media == Decimal("30")
        assert result.estatisticas.mediana == Decimal("30")

    def test_desvio_padrao(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100, 100]]
        result = analyzer.analisar(registros)
        assert result.estatisticas.desvio_padrao == Decimal("0")

    def test_minimo_maximo(self, analyzer):
        registros = [_registro(v) for v in [5, 15, 25, 35]]
        result = analyzer.analisar(registros)
        assert result.estatisticas.minimo == Decimal("5")
        assert result.estatisticas.maximo == Decimal("35")

    def test_total_registros(self, analyzer):
        registros = [_registro(v) for v in [10, 20, 30]]
        result = analyzer.analisar(registros)
        assert result.estatisticas.total_registros == 3

    def test_coeficiente_variacao_zero(self, analyzer):
        registros = [_registro(50) for _ in range(5)]
        result = analyzer.analisar(registros)
        assert result.estatisticas.coeficiente_variacao == Decimal("0")

    def test_coeficiente_variacao_alto(self, analyzer):
        registros = [_registro(v) for v in [10, 50, 100, 200]]
        result = analyzer.analisar(registros)
        assert result.estatisticas.coeficiente_variacao > Decimal("15")

    def test_registro_unico(self, analyzer):
        registros = [_registro(42)]
        result = analyzer.analisar(registros)
        assert result.estatisticas.media == Decimal("42")
        assert result.estatisticas.desvio_padrao == Decimal("0")
        assert result.estatisticas.total_registros == 1

    def test_sem_registros(self, analyzer):
        with pytest.raises(ValueError, match="ao menos 1"):
            analyzer.analisar([])


# ---------------------------------------------------------------------------
# Outliers via IQR
# ---------------------------------------------------------------------------

class TestOutliers:
    """Testes para detecção de outliers pelo método IQR."""

    def test_sem_outliers(self, analyzer):
        registros = [_registro(v) for v in [100, 102, 98, 101, 99]]
        result = analyzer.analisar(registros)
        assert result.estatisticas.outliers == []

    def test_outlier_superior(self, analyzer):
        # Valores normais + 1 outlier extremo
        registros = [_registro(v) for v in [10, 11, 12, 13, 14, 50]]
        result = analyzer.analisar(registros)
        assert Decimal("50") in result.estatisticas.outliers

    def test_outlier_inferior(self, analyzer):
        registros = [_registro(v) for v in [1, 100, 101, 102, 103, 104]]
        result = analyzer.analisar(registros)
        assert Decimal("1") in result.estatisticas.outliers

    def test_limites_iqr(self, analyzer):
        registros = [_registro(v) for v in [10, 20, 30, 40]]
        result = analyzer.analisar(registros)
        stats = result.estatisticas
        assert stats.iqr == stats.percentil_75 - stats.percentil_25
        assert stats.limite_inferior_outlier == stats.percentil_25 - Decimal("1.5") * stats.iqr
        assert stats.limite_superior_outlier == stats.percentil_75 + Decimal("1.5") * stats.iqr


# ---------------------------------------------------------------------------
# Tendência
# ---------------------------------------------------------------------------

class TestTendencia:
    """Testes para análise de tendência temporal."""

    def test_tendencia_subindo(self, analyzer):
        registros = [
            _registro(100, dias_atras=90),  # 3 meses atrás
            _registro(110, dias_atras=60),  # 2 meses atrás
            _registro(120, dias_atras=30),  # 1 mês atrás
            _registro(130, dias_atras=0),   # hoje
        ]
        result = analyzer.analisar(registros)
        assert result.tendencia is not None
        assert result.tendencia.direcao == Tendencia.SUBINDO
        assert result.tendencia.variacao_percentual > Decimal("0")

    def test_tendencia_descendo(self, analyzer):
        registros = [
            _registro(200, dias_atras=90),
            _registro(180, dias_atras=60),
            _registro(160, dias_atras=30),
            _registro(140, dias_atras=0),
        ]
        result = analyzer.analisar(registros)
        assert result.tendencia is not None
        assert result.tendencia.direcao == Tendencia.DESCENDO
        assert result.tendencia.variacao_percentual < Decimal("0")

    def test_tendencia_estavel(self, analyzer):
        registros = [
            _registro(100, dias_atras=90),
            _registro(101, dias_atras=60),
            _registro(99, dias_atras=30),
            _registro(100, dias_atras=0),
        ]
        result = analyzer.analisar(registros)
        assert result.tendencia is not None
        assert result.tendencia.direcao == Tendencia.ESTAVEL

    def test_sem_tendencia_poucos_registros(self, analyzer):
        registros = [_registro(100), _registro(200)]
        result = analyzer.analisar(registros)
        # Com 2 registros no mesmo dia → 1 mês → tendência estável
        assert result.tendencia is None or result.tendencia.direcao == Tendencia.ESTAVEL

    def test_r_quadrado_perfeito(self, analyzer):
        # Progressão perfeitamente linear
        registros = [
            _registro(100, dias_atras=120),
            _registro(200, dias_atras=90),
            _registro(300, dias_atras=60),
            _registro(400, dias_atras=30),
        ]
        result = analyzer.analisar(registros)
        assert result.tendencia is not None
        assert result.tendencia.confianca >= 0.99

    def test_coeficiente_angular(self, analyzer):
        registros = [
            _registro(100, dias_atras=90),
            _registro(200, dias_atras=60),
            _registro(300, dias_atras=30),
            _registro(400, dias_atras=0),
        ]
        result = analyzer.analisar(registros)
        assert result.tendencia is not None
        # Slope positivo: preço subindo ~100/mês
        assert result.tendencia.coeficiente_angular > Decimal("0")


# ---------------------------------------------------------------------------
# Regional
# ---------------------------------------------------------------------------

class TestRegional:
    """Testes para análise de preços por região."""

    def test_precos_regionais(self, analyzer):
        registros = [
            _registro(100, uf="SP"), _registro(110, uf="SP"), _registro(105, uf="SP"),
            _registro(80, uf="PE"), _registro(85, uf="PE"), _registro(82, uf="PE"),
        ]
        result = analyzer.analisar(registros)
        assert len(result.precos_regionais) == 2
        ufs = {r.uf for r in result.precos_regionais}
        assert "SP" in ufs
        assert "PE" in ufs

    def test_regional_desvio_percentual(self, analyzer):
        registros = [
            _registro(100, uf="SP"), _registro(100, uf="SP"),
            _registro(50, uf="PE"), _registro(50, uf="PE"),
        ]
        result = analyzer.analisar(registros)
        pe = next(r for r in result.precos_regionais if r.uf == "PE")
        # PE tem média 50, nacional 75 → desvio ≈ -33.33%
        assert pe.desvio_percentual_media_nacional < Decimal("0")

    def test_regional_uf_unica_ignorada(self, analyzer):
        # Só 1 registro por UF — abaixo do mínimo
        registros = [_registro(100, uf="SP"), _registro(80, uf="PE")]
        result = analyzer.analisar(registros)
        assert len(result.precos_regionais) == 0

    def test_sem_uf(self, analyzer):
        registros = [_registro(100), _registro(200)]
        result = analyzer.analisar(registros)
        assert result.precos_regionais == []


# ---------------------------------------------------------------------------
# Comparação com estimado
# ---------------------------------------------------------------------------

class TestComparacao:
    """Testes para comparação valor estimado vs mercado."""

    def test_estimado_acima(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("150"))
        assert result.comparacao is not None
        assert result.comparacao.situacao == "acima"
        assert result.comparacao.diferenca_percentual == Decimal("50")

    def test_estimado_abaixo(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("80"))
        assert result.comparacao is not None
        assert result.comparacao.situacao == "abaixo"
        assert result.comparacao.diferenca_percentual == Decimal("-20")

    def test_estimado_compativel(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("105"))
        assert result.comparacao is not None
        assert result.comparacao.situacao == "compativel"

    def test_sem_estimado(self, analyzer):
        registros = [_registro(v) for v in [100, 200]]
        result = analyzer.analisar(registros)
        assert result.comparacao is None

    def test_margem_compatibilidade(self, analyzer):
        # Exatamente no limite de 10% → ainda compatível
        registros = [_registro(v) for v in [100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("110"))
        assert result.comparacao.situacao == "compativel"


# ---------------------------------------------------------------------------
# Alertas
# ---------------------------------------------------------------------------

class TestAlertas:
    """Testes para geração de alertas."""

    def test_alerta_critico_estimado_alto(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("200"))
        alertas_criticos = [a for a in result.alertas if a.nivel == NivelAlerta.CRITICO]
        assert len(alertas_criticos) >= 1
        assert "acima" in alertas_criticos[0].mensagem.lower()

    def test_alerta_atencao_estimado_moderado(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("120"))
        atencao = [a for a in result.alertas if a.nivel == NivelAlerta.ATENCAO]
        assert any("acima" in a.mensagem.lower() for a in atencao)

    def test_alerta_estimado_abaixo(self, analyzer):
        registros = [_registro(v) for v in [100, 100, 100, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("50"))
        atencao = [a for a in result.alertas if a.nivel == NivelAlerta.ATENCAO]
        assert any("abaixo" in a.mensagem.lower() for a in atencao)

    def test_alerta_alta_dispersao(self, analyzer):
        registros = [_registro(v) for v in [10, 50, 100, 200, 500]]
        result = analyzer.analisar(registros)
        assert any("dispersão" in a.mensagem.lower() for a in result.alertas)

    def test_alerta_outliers(self, analyzer):
        registros = [_registro(v) for v in [10, 11, 12, 13, 14, 100]]
        result = analyzer.analisar(registros)
        assert any("atípico" in a.mensagem.lower() for a in result.alertas)

    def test_alerta_poucos_registros(self, analyzer):
        registros = [_registro(v) for v in [100, 200, 300]]
        result = analyzer.analisar(registros)
        assert any("registro" in a.mensagem.lower() for a in result.alertas)

    def test_sem_alertas_dados_ideais(self, analyzer):
        # 10 registros homogêneos, estimado compatível
        registros = [_registro(v) for v in [100, 101, 99, 102, 98, 100, 101, 99, 100, 100]]
        result = analyzer.analisar(registros, valor_estimado=Decimal("100"))
        # Não deve ter alertas críticos
        criticos = [a for a in result.alertas if a.nivel == NivelAlerta.CRITICO]
        assert len(criticos) == 0


# ---------------------------------------------------------------------------
# Sugestão de preço
# ---------------------------------------------------------------------------

class TestSugestao:
    """Testes para sugestão de preço competitivo."""

    def test_sugestao_percentil_30(self, analyzer):
        registros = [_registro(v) for v in range(10, 110, 10)]  # 10, 20, ..., 100
        result = analyzer.analisar(registros)
        assert result.sugestao is not None
        assert result.sugestao.percentil == 30
        # P30 de [10..100] deve estar entre P25 e P40
        assert result.sugestao.faixa_minima <= result.sugestao.valor_sugerido
        assert result.sugestao.valor_sugerido <= result.sugestao.faixa_maxima

    def test_sugestao_faixa(self, analyzer):
        registros = [_registro(v) for v in [50, 60, 70, 80, 90, 100]]
        result = analyzer.analisar(registros)
        # Faixa: P25 ≤ sugerido ≤ P40
        assert result.sugestao.faixa_minima <= result.sugestao.faixa_maxima

    def test_sugestao_registro_unico(self, analyzer):
        registros = [_registro(42)]
        result = analyzer.analisar(registros)
        assert result.sugestao.valor_sugerido == Decimal("42")
        assert result.sugestao.faixa_minima == Decimal("42")
        assert result.sugestao.faixa_maxima == Decimal("42")

    def test_sugestao_justificativa(self, analyzer):
        registros = [_registro(v) for v in [100, 200, 300]]
        result = analyzer.analisar(registros)
        assert "percentil" in result.sugestao.justificativa.lower()
        assert "3" in result.sugestao.justificativa  # 3 registros


# ---------------------------------------------------------------------------
# Filtro de período
# ---------------------------------------------------------------------------

class TestFiltroPeriodo:
    """Testes para filtragem temporal dos registros."""

    def test_filtra_ultimos_12_meses(self, analyzer):
        registros = [
            _registro(100, dias_atras=0),      # hoje
            _registro(200, dias_atras=180),    # 6 meses
            _registro(300, dias_atras=400),    # >12 meses
        ]
        result = analyzer.analisar(registros, meses=12)
        # O registro de 400 dias deve ser filtrado → média de (100+200)/2 = 150
        assert result.estatisticas.total_registros == 2
        assert result.estatisticas.media == Decimal("150")

    def test_fallback_sem_dados_no_periodo(self, analyzer):
        # Todos antigos — fallback usa tudo
        registros = [_registro(100, dias_atras=500), _registro(200, dias_atras=600)]
        result = analyzer.analisar(registros, meses=6)
        assert result.estatisticas.total_registros == 2

    def test_periodo_customizado(self, analyzer):
        registros = [
            _registro(100, dias_atras=0),
            _registro(200, dias_atras=100),
            _registro(300, dias_atras=200),
        ]
        # Apenas últimos 3 meses (90 dias)
        result = analyzer.analisar(registros, meses=3)
        assert result.estatisticas.total_registros == 1


# ---------------------------------------------------------------------------
# Modelo RegistroPreco
# ---------------------------------------------------------------------------

class TestRegistroPreco:
    """Testes para o modelo de entrada."""

    def test_campos_obrigatorios(self):
        r = RegistroPreco(
            descricao_item="Caneta",
            valor_unitario=Decimal("2.50"),
            data_referencia=datetime(2025, 1, 1),
        )
        assert r.fonte == FontePreco.INTERNO
        assert r.quantidade == Decimal("1")

    def test_todas_as_fontes(self):
        for fonte in FontePreco:
            r = RegistroPreco(
                descricao_item="Item",
                valor_unitario=Decimal("10"),
                data_referencia=datetime(2025, 1, 1),
                fonte=fonte,
            )
            assert r.fonte == fonte


# ---------------------------------------------------------------------------
# Análise completa (integração)
# ---------------------------------------------------------------------------

class TestAnaliseCompleta:
    """Teste de integração com cenário realista."""

    def test_cenario_limpeza_predial(self, analyzer):
        """Simula análise de preço para serviço de limpeza predial."""
        registros = [
            RegistroPreco(
                descricao_item="Limpeza predial - servente",
                valor_unitario=Decimal("2800"),
                data_referencia=datetime(2025, 1, 15),
                fonte=FontePreco.PNCP,
                uf="PE",
            ),
            RegistroPreco(
                descricao_item="Limpeza predial - servente",
                valor_unitario=Decimal("3000"),
                data_referencia=datetime(2025, 2, 10),
                fonte=FontePreco.PAINEL_PRECOS,
                uf="PE",
            ),
            RegistroPreco(
                descricao_item="Limpeza predial - servente",
                valor_unitario=Decimal("3200"),
                data_referencia=datetime(2025, 3, 5),
                fonte=FontePreco.PNCP,
                uf="SP",
            ),
            RegistroPreco(
                descricao_item="Limpeza predial - servente",
                valor_unitario=Decimal("3100"),
                data_referencia=datetime(2025, 3, 20),
                fonte=FontePreco.INTERNO,
                uf="SP",
            ),
            RegistroPreco(
                descricao_item="Limpeza predial - servente",
                valor_unitario=Decimal("2900"),
                data_referencia=datetime(2025, 4, 1),
                fonte=FontePreco.PNCP,
                uf="PE",
            ),
        ]

        result = analyzer.analisar(
            registros,
            descricao_item="Limpeza predial - servente (44h)",
            valor_estimado=Decimal("4500"),
        )

        # Estrutura completa
        assert result.descricao_item == "Limpeza predial - servente (44h)"
        assert result.estatisticas.total_registros == 5
        assert result.estatisticas.media > Decimal("0")

        # Estimado muito acima → deve ter alerta
        assert result.comparacao is not None
        assert result.comparacao.situacao == "acima"
        assert any(a.nivel == NivelAlerta.CRITICO for a in result.alertas)

        # Regionais: PE e SP (mas PE e SP têm poucos registros individualmente)
        # PE: 3 registros ≥ MIN_REGISTROS_REGIONAL, SP: 2 ≥ MIN_REGISTROS_REGIONAL
        pe_regs = [r for r in registros if r.uf == "PE"]
        sp_regs = [r for r in registros if r.uf == "SP"]
        if len(pe_regs) >= 2 and len(sp_regs) >= 2:
            assert len(result.precos_regionais) >= 2

        # Sugestão deve existir
        assert result.sugestao is not None
        assert result.sugestao.valor_sugerido > Decimal("0")
        assert result.sugestao.valor_sugerido < Decimal("4500")

    def test_descricao_item_padrao(self, analyzer):
        """Usa descrição do primeiro registro se não informada."""
        registros = [_registro(100)]
        result = analyzer.analisar(registros)
        assert result.descricao_item == "Material de limpeza"


# ---------------------------------------------------------------------------
# Regressão linear
# ---------------------------------------------------------------------------

class TestRegressaoLinear:
    """Testes para o método interno de regressão linear."""

    def test_linha_perfeita(self):
        slope, intercept, r2 = PriceAnalyzer._regressao_linear(
            [0, 1, 2, 3], [10, 20, 30, 40]
        )
        assert abs(slope - 10) < 0.01
        assert abs(intercept - 10) < 0.01
        assert r2 >= 0.99

    def test_constante(self):
        slope, intercept, r2 = PriceAnalyzer._regressao_linear(
            [0, 1, 2], [50, 50, 50]
        )
        assert abs(slope) < 0.01

    def test_dois_pontos(self):
        slope, intercept, r2 = PriceAnalyzer._regressao_linear(
            [0, 1], [100, 200]
        )
        assert abs(slope - 100) < 0.01
        assert r2 >= 0.99


# ---------------------------------------------------------------------------
# Percentil
# ---------------------------------------------------------------------------

class TestPercentil:
    """Testes para cálculo de percentil."""

    def test_percentil_mediano(self):
        vals = [10, 20, 30, 40, 50]
        p50 = PriceAnalyzer._percentil(vals, 50)
        assert abs(p50 - 30) < 0.01

    def test_percentil_extremos(self):
        vals = [10, 20, 30, 40, 50]
        p0 = PriceAnalyzer._percentil(vals, 0)
        p100 = PriceAnalyzer._percentil(vals, 100)
        assert abs(p0 - 10) < 0.01
        assert abs(p100 - 50) < 0.01

    def test_percentil_interpolacao(self):
        vals = [100, 200]
        p50 = PriceAnalyzer._percentil(vals, 50)
        assert abs(p50 - 150) < 0.01
