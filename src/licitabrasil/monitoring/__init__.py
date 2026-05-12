"""Módulo de monitoramento — consolida dados de todos os scrapers e gera
relatórios de prazos críticos.

Pensado para a Argus: cruza SQLite locais (PE-Integrado, FIEMG, CBTU,
JFPE, etc) e produz briefing por urgência (crítico/atenção/planejamento).
"""

from .prazos import (  # noqa: F401
    PrazoItem,
    Urgencia,
    coletar_prazos,
    formatar_briefing,
)
