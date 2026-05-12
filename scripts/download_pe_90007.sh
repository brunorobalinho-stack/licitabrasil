#!/bin/bash
# Baixa documentos da PE 90007/2025 STU Recife
DEST="/Users/brunorobalinho/Documents/Claude/Claude.Cowork/cbtu_pe_90007_2025"
mkdir -p "$DEST"
cd "$DEST" || exit 1

BASE="https://www.gov.br/cbtu/pt-br/acesso-a-informacao/receitas-e-despesas/licitacoes/cbtu-recife/pregoes-2025/pregao-9007-2025"

echo "Baixando 4 documentos para $DEST"

curl -sSL -o "00-edital.pdf" "$BASE/00-edital-limpeza-jardinagem-coperagem-para-eoa-e-cmc-v3-12-meses-pel-90007-2025.pdf" &
curl -sSL -o "01-tr-anexo1.pdf" "$BASE/01-anexo-i-do-edital-tr-limpeza-jardinagem-coperagem-para-eoa-e-cmc-pel-90007-2025.pdf" &
curl -sSL -o "01.1-planilha-custos-anexo3.xls" "$BASE/01-1-anexo-iii-do-tr-planilha-de-custos-e-formacao-de-precos-em-branco.xls" &
curl -sSL -o "02-minuta-contrato-anexo2.pdf" "$BASE/02-anexo-ii-do-edital-minuta-de-contrato-pel-90007-2025.pdf" &

wait
echo "DONE"
ls -la "$DEST"
