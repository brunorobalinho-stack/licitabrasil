# /recon - Reconhecimento de Portal

URL do portal: **$ARGUMENTS**

## Sequencia obrigatoria:
1. Fazer requisicao real (GET/POST) e capturar resposta
2. Analisar estrutura (HTML, JSON, XML)
3. Identificar paginacao, filtros, rate limits
4. Documentar endpoints em docstring
5. Salvar fixtures em tests/fixtures/

## Output:
Relatorio: tipo de portal, stack detectada, endpoints,
autenticacao, paginacao, rate limits, recomendacao
(httpx simples ou Playwright necessario).
