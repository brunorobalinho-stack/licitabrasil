"""Scraper de licitações do PE-Integrado (Portal de Compras de Pernambuco).

URL: https://www.peintegrado.pe.gov.br/

Cobre:
- Compras Diretas (CCD) — Dispensa de Licitação
- Pregões Eletrônicos (PE / NLCD-PE)
- Concorrências
- Inexigibilidades

Saída: SQLite local em ``data/peintegrado/peintegrado.db``.
"""
