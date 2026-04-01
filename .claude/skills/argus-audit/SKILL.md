---
name: argus-audit
description: Auditoria de folha para contratos Argus. REGRA No1 100pct verificacao.
---

# Auditoria Argus

REGRA No1: verificacao de 100% dos empregados. Zero amostragem.

## Ferramentas
- openpyxl para planilhas Excel
- pdfplumber para PDFs de folha
- pandas para cruzamento

## Fluxo
1. Carregar planilha de controle
2. Extrair dados do PDF
3. Cruzar nome a nome
4. Gerar relatorio de divergencias
