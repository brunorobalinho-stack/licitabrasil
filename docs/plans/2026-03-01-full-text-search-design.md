# Busca Full-Text com PostgreSQL tsvector

**Data:** 2026-03-01
**Status:** Aprovado
**Abordagem:** tsvector puro com trigger PostgreSQL

## Problema

A busca atual usa ILIKE no campo `objeto` apenas, sem ranking por relevancia, sem stemming em portugues, e sem destaque dos termos encontrados. A coluna `searchVector` (tsvector) e o indice GIN ja existem no schema mas nao estao sendo populados.

## Decisoes de Design

1. **tsvector puro** (sem pg_trgm fallback nesta iteracao)
2. **Busca integrada aos filtros** no endpoint unificado `GET /api/licitacoes`
3. **ts_headline** para highlight dos termos nos resultados
4. **Pesos diferenciados** por campo para ranking

## Camada de Dados

### Trigger PostgreSQL

Migration SQL que cria function + trigger para popular `searchVector` em INSERT/UPDATE.

Campos e pesos:

| Campo | Peso | Razao |
|-------|------|-------|
| objeto | A | Descricao principal da licitacao |
| orgao | B | Orgao contratante |
| palavras_chave (array->text) | B | Keywords do scraper |
| municipio + uf | C | Localizacao |
| numero_edital + codigo_pncp | D | Codigos de referencia |

A function usa `setweight(to_tsvector('portuguese', coalesce(campo, '')), peso)` concatenando com `||`.

A migration tambem executa UPDATE em todas as rows existentes para popular o searchVector.

### Indice

O indice GIN em `searchVector` ja existe no schema Prisma:
```
@@index([searchVector], type: Gin)
```

## Backend

### Endpoint Unificado GET /api/licitacoes

Logica do parametro `q`:
- Se `q` presente: usar `searchVector @@ to_tsquery('portuguese', q_sanitizado)` com `ts_rank(searchVector, query)` para ordenacao
- Se `q` vazio: comportamento atual (listar com filtros, ordenar por dataPublicacao)
- Filtros WHERE (esfera, UF, modalidade, status, valor, data) funcionam em conjunto com busca textual

### Sanitizacao da Query

1. Split por espacos
2. Remover caracteres especiais (manter apenas letras, numeros, espacos)
3. Join com `&` (AND semantics)
4. Aspas `"termo exato"` -> converter para `<->` (phrase search)
5. Fallback ILIKE caso searchVector nulo para alguma row

### Response

```json
{
  "data": [...],
  "pagination": { "page": 1, "pageSize": 20, "total": 42, "totalPages": 3 },
  "highlights": {
    "id_da_licitacao": "...servicos de <mark>agua potavel</mark> para..."
  }
}
```

O campo highlights e separado do data para nao poluir o objeto original. Gerado via `ts_headline('portuguese', objeto, query, 'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=30')`.

### Cache

Redis com 15min TTL, key baseada em SHA-256 hash de `q + filtros`.

## Frontend

### Zustand Store

Sem mudanca estrutural. O metodo `search()` ja envia `q` como parametro. O backend muda o comportamento internamente.

Store recebe `highlights` no response e armazena no state.

### LicitacaoCard

- Se `highlights[id]` existe: renderizar snippet com `<span dangerouslySetInnerHTML>` (apenas tags `<mark>`)
- Sanitizacao: strip de qualquer tag que nao seja `<mark>` e `</mark>`
- Fallback: sem highlight, mostra objeto truncado (comportamento atual)

### Ordenacao

- Quando `q` presente: ordenar por "Relevancia" automaticamente
- Select de ordenacao ganha opcao "Relevancia" (visivel apenas com texto de busca)
- Sem `q`: manter ordenacao padrao por dataPublicacao

## Fora de Escopo (proxima iteracao)

- Busca fuzzy com pg_trgm (tolerancia a typos)
- Autocomplete/sugestoes enquanto digita
- Sinonimos e expansao de query
- "Voce quis dizer?"
- Filtros avancados novos no UI (municipio, orgao, segmento)
- Operadores booleanos explicitos (AND/OR/NOT com sintaxe de usuario)

## Testes

- Teste unitario: sanitizacao de query (caracteres especiais, aspas, vazio)
- Teste de integracao: busca com tsvector retorna resultados ranqueados
- Teste de integracao: busca + filtros combinados
- Teste frontend: LicitacaoCard renderiza highlight corretamente
- Teste de regressao: busca vazia continua retornando todos os resultados
