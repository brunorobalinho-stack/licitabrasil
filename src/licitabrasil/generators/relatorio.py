"""Gerador de relatórios analíticos.

TODO: Implementar
- Relatório de licitações por período
- Relatório de matches por empresa
- Exportação em PDF/XLSX
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class RelatorioGenerator:
    """Gera relatórios analíticos de licitações."""

    def gerar_relatorio_periodo(self, dias: int = 30, output: Path | None = None) -> Path:
        """Gera relatório de licitações do período."""
        raise NotImplementedError("RelatorioGenerator ainda não implementado")

    def gerar_relatorio_matches(self, cnpj: str, output: Path | None = None) -> Path:
        """Gera relatório de matches para uma empresa."""
        raise NotImplementedError("RelatorioGenerator ainda não implementado")
