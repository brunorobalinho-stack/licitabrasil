"""Scraper de licitações da FIEMG Compras.

URL: https://licitacoes.compras.fiemg.com.br/

FIEMG (Federação das Indústrias do Estado de Minas Gerais) opera um portal
próprio de cotações com numeração SDE (Solicitação de Demanda Eletrônica).
Mesmo sendo entidade privada, publica licitações para fornecedores
externos — relevante para a Argus.

Saída: SQLite local em ``data/fiemg/fiemg.db``.
"""
