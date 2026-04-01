# /auditar-folha - Auditoria de Folha de Pagamento

Contrato alvo: **$ARGUMENTS**

## REGRA No1 (INVIOLAVEL)
Verificar 100% dos empregados. Zero amostragem. Sem excecoes.

## Metodologia:
1. Abrir planilha Excel de controle do contrato
2. Abrir PDF da folha de pagamento
3. Para CADA empregado na planilha:
   - Confirmar presenca na folha
   - Verificar: nome completo, cargo, salario base, adicionais
   - Sinalizar divergencias
4. Para CADA empregado na folha:
   - Confirmar presenca na planilha (detectar fantasmas)
5. Gerar relatorio de divergencias

## Output:
Tabela: empregado | status (OK/DIVERGENCIA) | detalhe
Resumo: total verificados, divergencias, acao necessaria.
