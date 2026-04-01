"""Classificador automático de licitações por segmento/CNAE.

TODO: Implementar
- Classificar objeto da licitação em segmentos
- Sugerir CNAEs baseado no texto
- Pode usar TF-IDF, regex patterns, ou modelo ML
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class LicitacaoClassifier:
    """Classifica licitações por segmento e CNAE."""

    def classificar_segmento(self, objeto: str) -> str | None:
        """Retorna o segmento provável da licitação."""
        raise NotImplementedError("Classificador ainda não implementado")

    def sugerir_cnaes(self, objeto: str) -> list[str]:
        """Retorna lista de CNAEs sugeridos para o objeto."""
        raise NotImplementedError("Classificador ainda não implementado")
