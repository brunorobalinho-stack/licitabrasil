# /vencimento - Check de Vencimentos

Verificar vencimentos de: **$ARGUMENTS**
Se vazio, verificar TODOS os contratos.

## Categorias:
- Contratos (data fim, prorrogacoes)
- Certidoes (CND FGTS, Federal, Municipal, CRF)
- Seguros-garantia
- Alvaras e licencas
- Certificacoes (PPRA, PCMSO)

## Output:
Tabela por urgencia: documento | contrato | vence | dias | acao
VERMELHO: < 15 dias | AMARELO: < 30 dias | VERDE: > 30 dias
