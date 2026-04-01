"""MatchEngine — matching ponderado entre empresa e licitacoes.

Criterios (5):
- CNAE: 0.30 (match exato ou grupo)
- Keywords TF-IDF: 0.25 (cosine similarity)
- Valor: 0.20 (dentro da faixa)
- Regiao: 0.15 (cidade/estado/regiao)
- Historico: 0.10 (placeholder v1)
"""

from __future__ import annotations

import logging
from decimal import Decimal

from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PerfilEmpresa(BaseModel):
    """Perfil de empresa para matching."""

    cnpj: str
    razao_social: str
    cnaes: list[str] = Field(default_factory=list)
    palavras_chave: list[str] = Field(default_factory=list)
    valor_minimo: Decimal | None = None
    valor_maximo: Decimal | None = None
    estados: list[str] = Field(default_factory=list)
    municipios: list[str] = Field(default_factory=list)
    modalidades: list[str] = Field(default_factory=list)


class LicitacaoParaMatch(BaseModel):
    """Dados minimos de uma licitacao para matching."""

    id: str
    objeto: str
    cnae: list[str] = Field(default_factory=list)
    valor_estimado: Decimal | None = None
    uf: str | None = None
    municipio: str | None = None
    orgao: str = ""


class MatchResult(BaseModel):
    """Resultado do matching para uma licitacao."""

    licitacao_id: str
    empresa_cnpj: str
    score_total: float = Field(ge=0.0, le=1.0)
    scores: dict[str, float] = Field(default_factory=dict)
    recomendacao: str  # "alta", "media", "baixa"


# ---------------------------------------------------------------------------
# Pesos
# ---------------------------------------------------------------------------

PESOS = {
    "cnae": 0.30,
    "keywords": 0.25,
    "valor": 0.20,
    "regiao": 0.15,
    "historico": 0.10,
}

# Mapeamento UF -> regiao
REGIOES: dict[str, str] = {
    "AC": "N", "AP": "N", "AM": "N", "PA": "N", "RO": "N", "RR": "N", "TO": "N",
    "AL": "NE", "BA": "NE", "CE": "NE", "MA": "NE", "PB": "NE", "PE": "NE",
    "PI": "NE", "RN": "NE", "SE": "NE",
    "DF": "CO", "GO": "CO", "MT": "CO", "MS": "CO",
    "ES": "SE", "MG": "SE", "RJ": "SE", "SP": "SE",
    "PR": "S", "RS": "S", "SC": "S",
}


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class MatchEngine:
    """Calcula score de matching entre empresa e licitacoes."""

    def __init__(self):
        """Inicializa o engine de matching."""
        self._vectorizer: TfidfVectorizer | None = None

    def calcular_matches(
        self,
        empresa: PerfilEmpresa,
        licitacoes: list[LicitacaoParaMatch],
        min_score: float = 0.3,
    ) -> list[MatchResult]:
        """Calcula matching para todas as licitacoes.

        Args:
            empresa: Perfil da empresa.
            licitacoes: Lista de licitacoes para avaliar.
            min_score: Score minimo para incluir no resultado.

        Returns:
            Lista de MatchResult ordenada por score (desc).
        """
        if not licitacoes:
            return []

        # Pre-computa TF-IDF
        keywords_scores = self._calcular_keywords_batch(empresa, licitacoes)

        results = []
        for i, lic in enumerate(licitacoes):
            scores = {
                "cnae": self._score_cnae(empresa, lic),
                "keywords": keywords_scores[i],
                "valor": self._score_valor(empresa, lic),
                "regiao": self._score_regiao(empresa, lic),
                "historico": 0.5,  # v1: neutro, sem dados de historico
            }

            total = sum(scores[k] * PESOS[k] for k in PESOS)

            if total >= min_score:
                results.append(MatchResult(
                    licitacao_id=lic.id,
                    empresa_cnpj=empresa.cnpj,
                    score_total=round(total, 3),
                    scores={k: round(v, 3) for k, v in scores.items()},
                    recomendacao=self._classificar(total),
                ))

        results.sort(key=lambda r: r.score_total, reverse=True)
        return results

    def _score_cnae(self, empresa: PerfilEmpresa, lic: LicitacaoParaMatch) -> float:
        """Score baseado em CNAE: exato=1.0, grupo(2 digitos)=0.4."""
        if not empresa.cnaes or not lic.cnae:
            return 0.0

        empresa_set = set(empresa.cnaes)
        lic_set = set(lic.cnae)

        # Match exato
        if empresa_set & lic_set:
            return 1.0

        # Match por grupo (primeiros 2 digitos)
        empresa_grupos = {c[:2] for c in empresa.cnaes if len(c) >= 2}
        lic_grupos = {c[:2] for c in lic.cnae if len(c) >= 2}
        if empresa_grupos & lic_grupos:
            return 0.4

        return 0.0

    def _calcular_keywords_batch(
        self,
        empresa: PerfilEmpresa,
        licitacoes: list[LicitacaoParaMatch],
    ) -> list[float]:
        """Calcula TF-IDF cosine similarity em batch."""
        if not empresa.palavras_chave:
            return [0.0] * len(licitacoes)

        empresa_text = " ".join(empresa.palavras_chave)
        corpus = [lic.objeto for lic in licitacoes]

        # Inclui o texto da empresa como primeiro documento
        all_docs = [empresa_text] + corpus

        try:
            vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words=None,  # Portugues nao tem stop words built-in no sklearn
            )
            tfidf_matrix = vectorizer.fit_transform(all_docs)

            # Similarity entre empresa (idx 0) e cada licitacao (idx 1..N)
            empresa_vec = tfidf_matrix[0:1]
            lic_matrix = tfidf_matrix[1:]
            similarities = cosine_similarity(empresa_vec, lic_matrix).flatten()
            return similarities.tolist()
        except Exception as e:
            logger.warning("Erro no TF-IDF: %s", e)
            return [0.0] * len(licitacoes)

    def _score_valor(self, empresa: PerfilEmpresa, lic: LicitacaoParaMatch) -> float:
        """Score baseado no valor estimado vs faixa da empresa."""
        if not lic.valor_estimado:
            return 0.5  # Sem valor = neutro

        val = float(lic.valor_estimado)
        vmin = float(empresa.valor_minimo) if empresa.valor_minimo else 0
        vmax = float(empresa.valor_maximo) if empresa.valor_maximo else float("inf")

        if not empresa.valor_minimo and not empresa.valor_maximo:
            return 0.5  # Sem faixa definida = neutro

        if vmin <= val <= vmax:
            return 1.0

        # Ate 50% fora da faixa
        if vmax != float("inf") and val > vmax:
            excesso = (val - vmax) / vmax if vmax > 0 else 1.0
            if excesso <= 0.5:
                return 0.5
            return 0.1

        if vmin > 0 and val < vmin:
            deficit = (vmin - val) / vmin
            if deficit <= 0.5:
                return 0.5
            return 0.1

        return 0.1

    def _score_regiao(self, empresa: PerfilEmpresa, lic: LicitacaoParaMatch) -> float:
        """Score baseado na localidade."""
        if not empresa.estados and not empresa.municipios:
            return 0.5  # Sem preferencia = neutro

        # Match por municipio
        if empresa.municipios and lic.municipio:
            lic_mun = lic.municipio.upper().strip()
            if any(m.upper().strip() == lic_mun for m in empresa.municipios):
                return 1.0

        # Match por estado
        if empresa.estados and lic.uf:
            lic_uf = lic.uf.upper().strip()
            if any(e.upper().strip() == lic_uf for e in empresa.estados):
                return 0.7

            # Match por regiao
            lic_regiao = REGIOES.get(lic_uf)
            empresa_regioes = {REGIOES.get(e.upper().strip()) for e in empresa.estados}
            if lic_regiao and lic_regiao in empresa_regioes:
                return 0.4

        return 0.1

    @staticmethod
    def _classificar(score: float) -> str:
        if score >= 0.7:
            return "alta"
        if score >= 0.45:
            return "media"
        return "baixa"
