"""PriceAnalyzer — análise de preços baseada em dados históricos de contratos públicos.

Fontes de dados suportadas:
1. PNCP — Atas de registro de preços, contratos homologados
2. Painel de Preços (paineldeprecos.planejamento.gov.br)
3. Banco de Preços em Saúde (BPS)
4. Histórico interno do LicitaBrasil

Análises:
- Preço médio por item/serviço nos últimos 12 meses
- Dispersão de preços (desvio padrão, outliers via IQR)
- Tendência de preços (subindo, descendo, estável)
- Preço praticado por região (UF)
- Comparação: valor estimado do órgão vs. preço real de mercado
- Sugestão de preço competitivo (percentil 25-40 do histórico)
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Sequence
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FontePreco(str, Enum):
    """Origem do registro de preço."""
    PNCP = "pncp"
    PAINEL_PRECOS = "painel_precos"
    BPS = "bps"
    INTERNO = "interno"


class Tendencia(str, Enum):
    """Direção da tendência de preço."""
    SUBINDO = "subindo"
    DESCENDO = "descendo"
    ESTAVEL = "estavel"


class NivelAlerta(str, Enum):
    """Severidade de um alerta de preço."""
    INFO = "info"
    ATENCAO = "atencao"
    CRITICO = "critico"


# ---------------------------------------------------------------------------
# Models de entrada
# ---------------------------------------------------------------------------

class RegistroPreco(BaseModel):
    """Registro individual de preço coletado de qualquer fonte.

    Modelo unificado: não importa se veio do PNCP, Painel de Preços ou BPS,
    todos são normalizados nesta estrutura.
    """
    descricao_item: str
    valor_unitario: Decimal
    quantidade: Decimal = Decimal("1")
    unidade: str = ""
    data_referencia: datetime
    fonte: FontePreco = FontePreco.INTERNO
    uf: str | None = None
    orgao: str | None = None
    numero_contrato: str | None = None
    codigo_catalogo: str | None = None


# ---------------------------------------------------------------------------
# Models de saída
# ---------------------------------------------------------------------------

class EstatisticasPreco(BaseModel):
    """Estatísticas descritivas de uma série de preços."""
    media: Decimal
    mediana: Decimal
    desvio_padrao: Decimal
    minimo: Decimal
    maximo: Decimal
    coeficiente_variacao: Decimal  # CV% = (stddev / media) * 100
    total_registros: int
    percentil_25: Decimal
    percentil_75: Decimal
    iqr: Decimal  # Interquartile range
    limite_inferior_outlier: Decimal  # Q1 - 1.5*IQR
    limite_superior_outlier: Decimal  # Q3 + 1.5*IQR
    outliers: list[Decimal] = Field(default_factory=list)


class TendenciaPreco(BaseModel):
    """Resultado da análise de tendência temporal."""
    direcao: Tendencia
    variacao_percentual: Decimal  # Variação do primeiro ao último período
    coeficiente_angular: Decimal  # Slope da regressão linear (R$/mês)
    confianca: float  # R² da regressão (0-1)


class PrecoRegional(BaseModel):
    """Preço médio praticado por UF."""
    uf: str
    media: Decimal
    mediana: Decimal
    total_registros: int
    desvio_percentual_media_nacional: Decimal  # % acima/abaixo da média nacional


class ComparacaoEstimado(BaseModel):
    """Comparação entre valor estimado pelo órgão e preço de mercado."""
    valor_estimado: Decimal
    media_mercado: Decimal
    diferenca_percentual: Decimal  # positivo = estimado acima do mercado
    situacao: str  # "acima", "abaixo", "compativel"


class AlertaPreco(BaseModel):
    """Alerta gerado pela análise de preços."""
    nivel: NivelAlerta
    mensagem: str
    detalhe: str | None = None


class SugestaoPreco(BaseModel):
    """Sugestão de preço competitivo."""
    percentil: int  # Ex: 30
    valor_sugerido: Decimal
    faixa_minima: Decimal  # Percentil 25
    faixa_maxima: Decimal  # Percentil 40
    justificativa: str


class AnalisePreco(BaseModel):
    """Resultado completo da análise de preços para um item."""
    descricao_item: str
    periodo_inicio: datetime
    periodo_fim: datetime
    estatisticas: EstatisticasPreco
    tendencia: TendenciaPreco | None = None
    precos_regionais: list[PrecoRegional] = Field(default_factory=list)
    comparacao: ComparacaoEstimado | None = None
    alertas: list[AlertaPreco] = Field(default_factory=list)
    sugestao: SugestaoPreco | None = None


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

# Meses para análise padrão
PERIODO_MESES_PADRAO = 12

# Limites para classificação de comparação estimado vs mercado
MARGEM_COMPATIVEL_PCT = Decimal("10")  # ±10% = compatível

# Faixa de percentis para preço competitivo
PERCENTIL_MIN = 25
PERCENTIL_MAX = 40
PERCENTIL_SUGESTAO = 30

# Coeficiente de variação máximo para considerar preços homogêneos
CV_HOMOGENEO_PCT = Decimal("15")

# Variação mínima para considerar tendência (e não "estável")
VARIACAO_MINIMA_TENDENCIA_PCT = Decimal("5")

# Mínimo de registros para análises avançadas
MIN_REGISTROS_TENDENCIA = 3
MIN_REGISTROS_REGIONAL = 2


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class PriceAnalyzer:
    """Analisa preços históricos de contratos públicos.

    Uso típico:
        analyzer = PriceAnalyzer()
        registros = [RegistroPreco(...), ...]
        resultado = analyzer.analisar(registros, "Material de limpeza")
    """

    def analisar(
        self,
        registros: list[RegistroPreco],
        descricao_item: str = "",
        valor_estimado: Decimal | None = None,
        meses: int = PERIODO_MESES_PADRAO,
    ) -> AnalisePreco:
        """Executa análise completa de preços.

        Args:
            registros: Lista de registros de preço históricos.
            descricao_item: Descrição do item analisado.
            valor_estimado: Valor estimado pelo órgão (para comparação).
            meses: Período de análise em meses (padrão: 12).

        Returns:
            AnalisePreco com todas as análises.

        Raises:
            ValueError: Se não houver registros.
        """
        if not registros:
            raise ValueError("Necessário ao menos 1 registro de preço para análise.")

        # Filtra por período
        filtrados = self._filtrar_periodo(registros, meses)
        if not filtrados:
            filtrados = registros  # Fallback: usa tudo se nada cair no período

        # Descrição: usa a do primeiro registro se não informada
        if not descricao_item:
            descricao_item = filtrados[0].descricao_item

        # Extrai valores para cálculos
        valores = [float(r.valor_unitario) for r in filtrados]
        datas = sorted(set(r.data_referencia for r in filtrados))

        # 1. Estatísticas descritivas
        stats = self._calcular_estatisticas(valores)

        # 2. Tendência
        tendencia = None
        if len(filtrados) >= MIN_REGISTROS_TENDENCIA:
            tendencia = self._calcular_tendencia(filtrados)

        # 3. Preços regionais
        regionais = self._calcular_regionais(filtrados, stats.media)

        # 4. Comparação com estimado
        comparacao = None
        if valor_estimado is not None:
            comparacao = self._comparar_estimado(valor_estimado, stats.media)

        # 5. Alertas
        alertas = self._gerar_alertas(stats, tendencia, comparacao)

        # 6. Sugestão de preço competitivo
        sugestao = self._sugerir_preco(valores)

        return AnalisePreco(
            descricao_item=descricao_item,
            periodo_inicio=min(datas),
            periodo_fim=max(datas),
            estatisticas=stats,
            tendencia=tendencia,
            precos_regionais=regionais,
            comparacao=comparacao,
            alertas=alertas,
            sugestao=sugestao,
        )

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _filtrar_periodo(
        self,
        registros: list[RegistroPreco],
        meses: int,
    ) -> list[RegistroPreco]:
        """Filtra registros dos últimos N meses."""
        if not registros:
            return []
        data_mais_recente = max(r.data_referencia for r in registros)
        corte = data_mais_recente - timedelta(days=meses * 30)
        return [r for r in registros if r.data_referencia >= corte]

    def _calcular_estatisticas(self, valores: list[float]) -> EstatisticasPreco:
        """Calcula estatísticas descritivas com detecção de outliers via IQR."""
        n = len(valores)
        sorted_vals = sorted(valores)

        media = statistics.mean(sorted_vals)
        mediana = statistics.median(sorted_vals)
        desvio = statistics.stdev(sorted_vals) if n >= 2 else 0.0
        cv = (desvio / media * 100) if media > 0 else 0.0

        # Percentis via interpolação linear
        if n >= 2:
            quantis = statistics.quantiles(sorted_vals, n=4)
            q1, _, q3 = quantis[0], quantis[1], quantis[2]
        else:
            q1 = q3 = sorted_vals[0]

        iqr = q3 - q1
        lim_inf = q1 - 1.5 * iqr
        lim_sup = q3 + 1.5 * iqr
        outliers = [v for v in sorted_vals if v < lim_inf or v > lim_sup]

        return EstatisticasPreco(
            media=self._dec(media),
            mediana=self._dec(mediana),
            desvio_padrao=self._dec(desvio),
            minimo=self._dec(sorted_vals[0]),
            maximo=self._dec(sorted_vals[-1]),
            coeficiente_variacao=self._dec(cv),
            total_registros=n,
            percentil_25=self._dec(q1),
            percentil_75=self._dec(q3),
            iqr=self._dec(iqr),
            limite_inferior_outlier=self._dec(lim_inf),
            limite_superior_outlier=self._dec(lim_sup),
            outliers=[self._dec(v) for v in outliers],
        )

    def _calcular_tendencia(
        self,
        registros: list[RegistroPreco],
    ) -> TendenciaPreco:
        """Tendência via regressão linear simples sobre preço médio mensal.

        Agrupa por mês, calcula média mensal, faz regressão linear
        (mínimos quadrados) para determinar slope e R².
        """
        # Agrupa por ano-mês, calcula média
        por_mes: dict[str, list[float]] = {}
        for r in registros:
            chave = r.data_referencia.strftime("%Y-%m")
            por_mes.setdefault(chave, []).append(float(r.valor_unitario))

        meses_ordenados = sorted(por_mes.keys())
        if len(meses_ordenados) < 2:
            # Dados de 1 mês só — estável por definição
            return TendenciaPreco(
                direcao=Tendencia.ESTAVEL,
                variacao_percentual=Decimal("0"),
                coeficiente_angular=Decimal("0"),
                confianca=0.0,
            )

        medias = [statistics.mean(por_mes[m]) for m in meses_ordenados]
        x = list(range(len(medias)))  # 0, 1, 2, ...

        # Regressão linear: y = a + bx
        slope, intercept, r_squared = self._regressao_linear(x, medias)

        # Variação percentual primeiro → último
        primeiro = medias[0]
        ultimo = medias[-1]
        variacao_pct = ((ultimo - primeiro) / primeiro * 100) if primeiro != 0 else 0.0

        # Classificação
        if abs(variacao_pct) < float(VARIACAO_MINIMA_TENDENCIA_PCT):
            direcao = Tendencia.ESTAVEL
        elif variacao_pct > 0:
            direcao = Tendencia.SUBINDO
        else:
            direcao = Tendencia.DESCENDO

        return TendenciaPreco(
            direcao=direcao,
            variacao_percentual=self._dec(variacao_pct),
            coeficiente_angular=self._dec(slope),
            confianca=round(r_squared, 3),
        )

    def _calcular_regionais(
        self,
        registros: list[RegistroPreco],
        media_nacional: Decimal,
    ) -> list[PrecoRegional]:
        """Agrupa preços por UF e calcula estatísticas regionais."""
        por_uf: dict[str, list[float]] = {}
        for r in registros:
            if r.uf:
                por_uf.setdefault(r.uf.upper(), []).append(float(r.valor_unitario))

        media_nac = float(media_nacional) if media_nacional else 1.0
        resultado = []

        for uf in sorted(por_uf.keys()):
            vals = por_uf[uf]
            if len(vals) < MIN_REGISTROS_REGIONAL:
                continue

            media_uf = statistics.mean(vals)
            desvio_pct = ((media_uf - media_nac) / media_nac * 100) if media_nac > 0 else 0.0

            resultado.append(PrecoRegional(
                uf=uf,
                media=self._dec(media_uf),
                mediana=self._dec(statistics.median(vals)),
                total_registros=len(vals),
                desvio_percentual_media_nacional=self._dec(desvio_pct),
            ))

        return resultado

    def _comparar_estimado(
        self,
        valor_estimado: Decimal,
        media_mercado: Decimal,
    ) -> ComparacaoEstimado:
        """Compara valor estimado pelo órgão com média de mercado."""
        est = float(valor_estimado)
        merc = float(media_mercado)

        if merc > 0:
            diff_pct = (est - merc) / merc * 100
        else:
            diff_pct = 0.0

        margem = float(MARGEM_COMPATIVEL_PCT)
        if diff_pct > margem:
            situacao = "acima"
        elif diff_pct < -margem:
            situacao = "abaixo"
        else:
            situacao = "compativel"

        return ComparacaoEstimado(
            valor_estimado=valor_estimado,
            media_mercado=media_mercado,
            diferenca_percentual=self._dec(diff_pct),
            situacao=situacao,
        )

    def _gerar_alertas(
        self,
        stats: EstatisticasPreco,
        tendencia: TendenciaPreco | None,
        comparacao: ComparacaoEstimado | None,
    ) -> list[AlertaPreco]:
        """Gera alertas baseados nos resultados das análises."""
        alertas: list[AlertaPreco] = []

        # Alerta: valor estimado muito acima do mercado
        if comparacao and comparacao.situacao == "acima":
            diff = abs(comparacao.diferenca_percentual)
            if diff > 30:
                alertas.append(AlertaPreco(
                    nivel=NivelAlerta.CRITICO,
                    mensagem=f"Valor estimado {diff:.0f}% acima da média de mercado",
                    detalhe=(
                        f"Estimado: R$ {comparacao.valor_estimado:,.2f} | "
                        f"Mercado: R$ {comparacao.media_mercado:,.2f}"
                    ),
                ))
            else:
                alertas.append(AlertaPreco(
                    nivel=NivelAlerta.ATENCAO,
                    mensagem=f"Valor estimado {diff:.0f}% acima da média de mercado",
                ))

        # Alerta: valor estimado abaixo do mercado
        if comparacao and comparacao.situacao == "abaixo":
            diff = abs(comparacao.diferenca_percentual)
            alertas.append(AlertaPreco(
                nivel=NivelAlerta.ATENCAO,
                mensagem=f"Valor estimado {diff:.0f}% abaixo da média de mercado",
                detalhe="Risco de deserto ou propostas com sobrepreço em aditivos",
            ))

        # Alerta: alta dispersão de preços
        if stats.coeficiente_variacao > CV_HOMOGENEO_PCT:
            alertas.append(AlertaPreco(
                nivel=NivelAlerta.ATENCAO,
                mensagem=f"Alta dispersão de preços (CV={stats.coeficiente_variacao:.1f}%)",
                detalhe="Preços pouco homogêneos — avaliar se os itens são comparáveis",
            ))

        # Alerta: outliers detectados
        if stats.outliers:
            alertas.append(AlertaPreco(
                nivel=NivelAlerta.INFO,
                mensagem=f"{len(stats.outliers)} valor(es) atípico(s) detectado(s)",
                detalhe=(
                    f"Faixa normal: R$ {stats.limite_inferior_outlier:,.2f} a "
                    f"R$ {stats.limite_superior_outlier:,.2f}"
                ),
            ))

        # Alerta: tendência de alta
        if tendencia and tendencia.direcao == Tendencia.SUBINDO:
            alertas.append(AlertaPreco(
                nivel=NivelAlerta.INFO,
                mensagem=f"Preços em tendência de alta ({tendencia.variacao_percentual:+.1f}%)",
            ))

        # Alerta: poucos registros
        if stats.total_registros < 5:
            alertas.append(AlertaPreco(
                nivel=NivelAlerta.ATENCAO,
                mensagem=f"Apenas {stats.total_registros} registro(s) encontrado(s)",
                detalhe="Base de comparação reduzida — considerar outras fontes",
            ))

        return alertas

    def _sugerir_preco(self, valores: list[float]) -> SugestaoPreco:
        """Sugere preço competitivo baseado em percentis do histórico."""
        sorted_vals = sorted(valores)
        n = len(sorted_vals)

        if n < 2:
            val = sorted_vals[0]
            return SugestaoPreco(
                percentil=PERCENTIL_SUGESTAO,
                valor_sugerido=self._dec(val),
                faixa_minima=self._dec(val),
                faixa_maxima=self._dec(val),
                justificativa=(
                    "Apenas 1 registro disponível — sugestão baseada no único valor"
                ),
            )

        # Calcula percentis 25, 30, 40
        p25 = self._percentil(sorted_vals, PERCENTIL_MIN)
        p30 = self._percentil(sorted_vals, PERCENTIL_SUGESTAO)
        p40 = self._percentil(sorted_vals, PERCENTIL_MAX)

        return SugestaoPreco(
            percentil=PERCENTIL_SUGESTAO,
            valor_sugerido=self._dec(p30),
            faixa_minima=self._dec(p25),
            faixa_maxima=self._dec(p40),
            justificativa=(
                f"Baseado no percentil {PERCENTIL_SUGESTAO} de {n} registros. "
                f"Faixa competitiva: P{PERCENTIL_MIN}–P{PERCENTIL_MAX}"
            ),
        )

    # ------------------------------------------------------------------
    # Utilitários matemáticos
    # ------------------------------------------------------------------

    @staticmethod
    def _regressao_linear(
        x: Sequence[int | float],
        y: Sequence[float],
    ) -> tuple[float, float, float]:
        """Regressão linear simples por mínimos quadrados.

        Returns:
            (slope, intercept, r_squared)
        """
        n = len(x)
        if n < 2:
            return 0.0, y[0] if y else 0.0, 0.0

        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)

        denom = n * sum_x2 - sum_x ** 2
        if denom == 0:
            return 0.0, statistics.mean(y), 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        # R² (coeficiente de determinação)
        ss_res = sum((yi - (intercept + slope * xi)) ** 2 for xi, yi in zip(x, y))
        mean_y = sum_y / n
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        r_squared = max(0.0, min(1.0, r_squared))  # Clamp [0, 1]

        return slope, intercept, r_squared

    @staticmethod
    def _percentil(sorted_vals: list[float], p: int) -> float:
        """Calcula percentil via interpolação linear (como Excel PERCENTILE.INC)."""
        n = len(sorted_vals)
        if n == 1:
            return sorted_vals[0]

        k = (p / 100) * (n - 1)
        f = int(k)
        c = f + 1 if f + 1 < n else f
        d = k - f

        return sorted_vals[f] + d * (sorted_vals[c] - sorted_vals[f])

    @staticmethod
    def _dec(value: float, places: int = 2) -> Decimal:
        """Converte float para Decimal arredondado."""
        return Decimal(str(round(value, places)))
