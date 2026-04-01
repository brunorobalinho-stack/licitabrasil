# Full-Text Search Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add PostgreSQL tsvector-based full-text search with weighted fields, ts_headline highlights, and relevance ranking to the unified `GET /api/licitacoes` endpoint.

**Architecture:** A PostgreSQL trigger populates a `searchVector` tsvector column with weighted fields on INSERT/UPDATE. The existing `GET /api/licitacoes` endpoint detects the `q` parameter and switches from ILIKE to `searchVector @@ to_tsquery()` with `ts_rank()` ordering. The response adds a `highlights` map generated via `ts_headline()`. The frontend store and card component render highlighted snippets.

**Tech Stack:** PostgreSQL 16 (tsvector, ts_rank, ts_headline), Prisma 6 ($queryRawUnsafe), Vitest + supertest, React 19 + Zustand + TypeScript

---

### Task 1: Create the search vector trigger migration

**Files:**
- Create: `backend/prisma/migrations/20260301000000_search_vector_trigger/migration.sql`

**Step 1: Write the migration SQL**

Create the migration file with the trigger function and backfill:

```sql
-- =============================================================================
-- Full-text search: trigger to populate searchVector on INSERT/UPDATE
-- =============================================================================

-- Function that builds a weighted tsvector from multiple fields
CREATE OR REPLACE FUNCTION licitacao_search_vector_update() RETURNS trigger AS $$
BEGIN
  NEW."searchVector" :=
    setweight(to_tsvector('portuguese', coalesce(NEW.objeto, '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.orgao, '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(array_to_string(NEW."palavrasChave", ' '), '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(NEW.municipio, '') || ' ' || coalesce(NEW.uf, '')), 'C') ||
    setweight(to_tsvector('portuguese', coalesce(NEW."numeroEdital", '') || ' ' || coalesce(NEW."codigoPNCP", '')), 'D');
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger on INSERT and UPDATE
CREATE TRIGGER trg_licitacao_search_vector
  BEFORE INSERT OR UPDATE ON "Licitacao"
  FOR EACH ROW
  EXECUTE FUNCTION licitacao_search_vector_update();

-- Backfill all existing rows
UPDATE "Licitacao" SET
  "searchVector" =
    setweight(to_tsvector('portuguese', coalesce(objeto, '')), 'A') ||
    setweight(to_tsvector('portuguese', coalesce(orgao, '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(array_to_string("palavrasChave", ' '), '')), 'B') ||
    setweight(to_tsvector('portuguese', coalesce(municipio, '') || ' ' || coalesce(uf, '')), 'C') ||
    setweight(to_tsvector('portuguese', coalesce("numeroEdital", '') || ' ' || coalesce("codigoPNCP", '')), 'D');
```

**Step 2: Apply the migration**

Run: `cd backend && npx prisma migrate deploy`
Expected: Migration applied successfully, no errors.

**Step 3: Verify the backfill worked**

Run: `cd backend && npx prisma db execute --stdin <<< "SELECT COUNT(*) FROM \"Licitacao\" WHERE \"searchVector\" IS NOT NULL;"`
Expected: Count matches total rows (150+).

Run: `cd backend && npx prisma db execute --stdin <<< "SELECT id, ts_rank(\"searchVector\", to_tsquery('portuguese', 'saude')) as rank FROM \"Licitacao\" WHERE \"searchVector\" @@ to_tsquery('portuguese', 'saude') ORDER BY rank DESC LIMIT 3;"`
Expected: Returns rows with non-zero rank scores.

**Step 4: Commit**

```bash
git add backend/prisma/migrations/20260301000000_search_vector_trigger/migration.sql
git commit -m "feat(db): add tsvector trigger and backfill searchVector"
```

---

### Task 2: Extract and test query sanitization

**Files:**
- Create: `backend/src/lib/search-query.ts`
- Create: `backend/tests/unit/search-query.test.ts`

**Step 1: Write the failing tests**

```typescript
// backend/tests/unit/search-query.test.ts
import { describe, it, expect } from 'vitest';
import { sanitizeSearchQuery } from '../../src/lib/search-query.js';

describe('sanitizeSearchQuery', () => {
  it('joins words with & for AND semantics', () => {
    expect(sanitizeSearchQuery('agua potavel')).toBe('agua & potavel');
  });

  it('strips special characters', () => {
    expect(sanitizeSearchQuery('serviço@#$ limpeza!')).toBe('serviço & limpeza');
  });

  it('handles accented Portuguese characters', () => {
    expect(sanitizeSearchQuery('manutenção predial')).toBe('manutenção & predial');
  });

  it('converts quoted phrases to <-> (phrase search)', () => {
    expect(sanitizeSearchQuery('"agua potavel" tratamento')).toBe('agua <-> potavel & tratamento');
  });

  it('returns null for empty/whitespace input', () => {
    expect(sanitizeSearchQuery('')).toBeNull();
    expect(sanitizeSearchQuery('   ')).toBeNull();
  });

  it('returns null for input with only special characters', () => {
    expect(sanitizeSearchQuery('@#$%')).toBeNull();
  });

  it('handles single word', () => {
    expect(sanitizeSearchQuery('hospital')).toBe('hospital');
  });

  it('collapses multiple spaces', () => {
    expect(sanitizeSearchQuery('agua    potavel')).toBe('agua & potavel');
  });
});
```

**Step 2: Run tests to verify they fail**

Run: `cd backend && npx vitest run tests/unit/search-query.test.ts`
Expected: FAIL — module `search-query.js` not found.

**Step 3: Write the implementation**

```typescript
// backend/src/lib/search-query.ts

/**
 * Sanitizes a user search query into a valid PostgreSQL tsquery string.
 *
 * Rules:
 * - Splits on whitespace, joins with & (AND semantics)
 * - Strips non-alphanumeric characters (keeps accented chars)
 * - Converts "quoted phrases" to <-> (FOLLOWED BY operator for phrase search)
 * - Returns null if nothing remains after sanitization
 */
export function sanitizeSearchQuery(raw: string): string | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;

  const parts: string[] = [];

  // Extract quoted phrases first
  const withoutPhrases = trimmed.replace(/"([^"]+)"/g, (_match, phrase: string) => {
    const words = phrase
      .split(/\s+/)
      .map((w) => w.replace(/[^a-zA-Z0-9À-ÿ]/g, ''))
      .filter(Boolean);
    if (words.length > 0) {
      parts.push(words.join(' <-> '));
    }
    return ''; // remove from remaining string
  });

  // Process remaining words
  const remainingWords = withoutPhrases
    .split(/\s+/)
    .map((w) => w.replace(/[^a-zA-Z0-9À-ÿ]/g, ''))
    .filter(Boolean);

  parts.push(...remainingWords);

  if (parts.length === 0) return null;
  return parts.join(' & ');
}
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && npx vitest run tests/unit/search-query.test.ts`
Expected: All 8 tests PASS.

**Step 5: Commit**

```bash
git add backend/src/lib/search-query.ts backend/tests/unit/search-query.test.ts
git commit -m "feat(search): add sanitizeSearchQuery with TDD"
```

---

### Task 3: Modify the GET /api/licitacoes endpoint to use tsvector

**Files:**
- Modify: `backend/src/api/routes/licitacoes.ts` (lines 94-240)
- Modify: `backend/tests/unit/licitacoes.test.ts`

**Step 1: Write the failing tests for the new search behavior**

Add these tests to `backend/tests/unit/licitacoes.test.ts` inside the existing `describe('GET /api/licitacoes')` block:

```typescript
  it('uses tsvector search when q is provided', async () => {
    mockPrisma.$queryRawUnsafe
      .mockResolvedValueOnce([{ count: BigInt(2) }]) // count query
      .mockResolvedValueOnce([sampleLicitacao]);       // data query

    const res = await request(app).get('/api/licitacoes?q=equipamentos');

    expect(res.status).toBe(200);
    expect(mockPrisma.$queryRawUnsafe).toHaveBeenCalled();
    // Should NOT use Prisma findMany for the data query
    expect(mockPrisma.licitacao.findMany).not.toHaveBeenCalled();
  });

  it('includes highlights map when q is provided', async () => {
    mockPrisma.$queryRawUnsafe
      .mockResolvedValueOnce([{ count: BigInt(1) }])
      .mockResolvedValueOnce([{
        ...sampleLicitacao,
        rank: 0.5,
        headline: 'Aquisição de <mark>equipamentos</mark>',
      }]);

    const res = await request(app).get('/api/licitacoes?q=equipamentos');

    expect(res.status).toBe(200);
    expect(res.body.highlights).toBeDefined();
    expect(res.body.highlights[sampleLicitacao.id]).toContain('<mark>');
  });

  it('falls back to ILIKE when tsvector query fails', async () => {
    mockPrisma.$queryRawUnsafe.mockRejectedValue(new Error('syntax error'));
    mockPrisma.licitacao.findMany.mockResolvedValue([sampleLicitacao]);
    mockPrisma.licitacao.count.mockResolvedValue(1);

    const res = await request(app).get('/api/licitacoes?q=equipamentos');

    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(1);
    expect(res.body.highlights).toEqual({});
  });

  it('applies filters alongside tsvector search', async () => {
    mockPrisma.$queryRawUnsafe
      .mockResolvedValueOnce([{ count: BigInt(0) }])
      .mockResolvedValueOnce([]);

    const res = await request(app).get('/api/licitacoes?q=equipamentos&esfera=FEDERAL&uf=SP');

    expect(res.status).toBe(200);
    // The SQL should contain WHERE clauses for both tsvector AND filters
    const sql = mockPrisma.$queryRawUnsafe.mock.calls[0][0];
    expect(sql).toContain('searchVector');
    expect(sql).toContain('esfera');
    expect(sql).toContain('uf');
  });

  it('orders by relevance when q is provided and ordenarPor is relevancia', async () => {
    mockPrisma.$queryRawUnsafe
      .mockResolvedValueOnce([{ count: BigInt(1) }])
      .mockResolvedValueOnce([{ ...sampleLicitacao, rank: 0.8, headline: 'test' }]);

    const res = await request(app).get('/api/licitacoes?q=equipamentos&ordenarPor=relevancia');

    expect(res.status).toBe(200);
    const sql = mockPrisma.$queryRawUnsafe.mock.calls[1][0];
    expect(sql).toContain('rank DESC');
  });
```

**Step 2: Run tests to verify the new ones fail**

Run: `cd backend && npx vitest run tests/unit/licitacoes.test.ts`
Expected: New tests FAIL (current code uses findMany + ILIKE for `q`).

**Step 3: Implement the tsvector search in the route handler**

Modify `backend/src/api/routes/licitacoes.ts`:

1. Add import at top:
```typescript
import { sanitizeSearchQuery } from '../../lib/search-query.js';
```

2. Replace the `GET /` handler (lines 180-240) with a new version that branches on `q`:

```typescript
router.get('/', asyncHandler(async (req, res) => {
  const params = listQuerySchema.parse(req.query);
  const cacheKey = `licitacoes:list:${hashQuery(params)}`;

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const skip = (params.page - 1) * params.pageSize;
  const tsQuery = params.q ? sanitizeSearchQuery(params.q) : null;

  // ── Full-text search path ──────────────────────────────────────────
  if (tsQuery) {
    try {
      const result = await fullTextSearch(params, tsQuery, skip);
      await cache.set(cacheKey, result, 900);
      res.json(result);
      return;
    } catch (err) {
      logger.warn({ err }, 'Full-text search fallback to ILIKE');
      // Fall through to standard path with ILIKE
    }
  }

  // ── Standard path (no q, or fallback) ──────────────────────────────
  const where = buildWhereClause(params);
  const orderBy = buildOrderBy(params.ordenarPor, params.ordem);

  const [data, total] = await Promise.all([
    prisma.licitacao.findMany({
      where,
      orderBy,
      skip,
      take: params.pageSize,
      select: listSelect,
    }),
    prisma.licitacao.count({ where }),
  ]);

  const totalPages = Math.ceil(total / params.pageSize);
  const result = {
    data,
    pagination: { page: params.page, pageSize: params.pageSize, total, totalPages },
    highlights: {} as Record<string, string>,
  };

  await cache.set(cacheKey, result, 900);
  res.json(result);
}));
```

3. Extract the select clause into a constant and add the `fullTextSearch` helper:

```typescript
const listSelect = {
  id: true,
  numeroEdital: true,
  numeroProcesso: true,
  codigoPNCP: true,
  modalidade: true,
  tipo: true,
  orgao: true,
  orgaoSigla: true,
  esfera: true,
  uf: true,
  municipio: true,
  objeto: true,
  objetoResumido: true,
  valorEstimado: true,
  dataPublicacao: true,
  dataAbertura: true,
  status: true,
  segmento: true,
  fonteOrigem: true,
  urlOrigem: true,
  criadoEm: true,
};

async function fullTextSearch(
  params: z.infer<typeof listQuerySchema>,
  tsQuery: string,
  skip: number,
) {
  // Build WHERE conditions for filters (excluding q — that uses tsvector)
  const conditions: string[] = [
    `"searchVector" @@ to_tsquery('portuguese', $1)`,
  ];
  const queryParams: unknown[] = [tsQuery];
  let paramIndex = 2;

  if (params.esfera) {
    conditions.push(`esfera = $${paramIndex}::\"Esfera\"`);
    queryParams.push(params.esfera);
    paramIndex++;
  }
  if (params.uf) {
    conditions.push(`uf = $${paramIndex}`);
    queryParams.push(params.uf.toUpperCase());
    paramIndex++;
  }
  if (params.municipio) {
    conditions.push(`municipio ILIKE $${paramIndex}`);
    queryParams.push(`%${params.municipio}%`);
    paramIndex++;
  }
  if (params.modalidade) {
    conditions.push(`modalidade = $${paramIndex}::\"Modalidade\"`);
    queryParams.push(params.modalidade);
    paramIndex++;
  }
  if (params.tipo) {
    conditions.push(`tipo = $${paramIndex}::\"TipoLicitacao\"`);
    queryParams.push(params.tipo);
    paramIndex++;
  }
  if (params.status) {
    conditions.push(`status = $${paramIndex}::\"StatusLicitacao\"`);
    queryParams.push(params.status);
    paramIndex++;
  }
  if (params.segmento) {
    conditions.push(`segmento ILIKE $${paramIndex}`);
    queryParams.push(`%${params.segmento}%`);
    paramIndex++;
  }
  if (params.orgao) {
    conditions.push(`orgao ILIKE $${paramIndex}`);
    queryParams.push(`%${params.orgao}%`);
    paramIndex++;
  }
  if (params.valorMin !== undefined) {
    conditions.push(`"valorEstimado" >= $${paramIndex}`);
    queryParams.push(params.valorMin);
    paramIndex++;
  }
  if (params.valorMax !== undefined) {
    conditions.push(`"valorEstimado" <= $${paramIndex}`);
    queryParams.push(params.valorMax);
    paramIndex++;
  }
  if (params.dataPublicacaoInicio) {
    conditions.push(`"dataPublicacao" >= $${paramIndex}::timestamptz`);
    queryParams.push(params.dataPublicacaoInicio);
    paramIndex++;
  }
  if (params.dataPublicacaoFim) {
    conditions.push(`"dataPublicacao" <= $${paramIndex}::timestamptz`);
    queryParams.push(params.dataPublicacaoFim);
    paramIndex++;
  }
  if (params.dataAberturaInicio) {
    conditions.push(`"dataAbertura" >= $${paramIndex}::timestamptz`);
    queryParams.push(params.dataAberturaInicio);
    paramIndex++;
  }
  if (params.dataAberturaFim) {
    conditions.push(`"dataAbertura" <= $${paramIndex}::timestamptz`);
    queryParams.push(params.dataAberturaFim);
    paramIndex++;
  }
  if (params.fonteOrigem) {
    conditions.push(`"fonteOrigem" = $${paramIndex}`);
    queryParams.push(params.fonteOrigem);
    paramIndex++;
  }

  const whereClause = conditions.join(' AND ');

  // Determine ORDER BY
  const orderBy = params.ordenarPor === 'relevancia' || !params.ordenarPor || params.ordenarPor === 'dataPublicacao'
    ? `ts_rank("searchVector", to_tsquery('portuguese', $1)) DESC`
    : params.ordenarPor === 'dataAbertura'
      ? `"dataAbertura" ${params.ordem}`
      : params.ordenarPor === 'valorEstimado'
        ? `"valorEstimado" ${params.ordem}`
        : `ts_rank("searchVector", to_tsquery('portuguese', $1)) DESC`;

  // When q is present and ordenarPor is not explicitly set, default to relevance
  const effectiveOrderBy = params.q
    ? (params.ordenarPor === 'dataAbertura' || params.ordenarPor === 'valorEstimado'
        ? `"${params.ordenarPor}" ${params.ordem}`
        : `ts_rank("searchVector", to_tsquery('portuguese', $1)) DESC`)
    : orderBy;

  // Count
  const countResult = await prisma.$queryRawUnsafe<[{ count: bigint }]>(
    `SELECT COUNT(*) as count FROM "Licitacao" WHERE ${whereClause}`,
    ...queryParams,
  );
  const total = Number(countResult[0].count);

  // Data with rank and headline
  const limitParam = `$${paramIndex}`;
  queryParams.push(params.pageSize);
  paramIndex++;
  const offsetParam = `$${paramIndex}`;
  queryParams.push(skip);

  const rows = await prisma.$queryRawUnsafe<Array<Record<string, unknown>>>(
    `SELECT id, "numeroEdital", "numeroProcesso", "codigoPNCP",
            modalidade, tipo, orgao, "orgaoSigla", esfera, uf, municipio,
            objeto, "objetoResumido", "valorEstimado",
            "dataPublicacao", "dataAbertura", status, segmento,
            "fonteOrigem", "urlOrigem", "criadoEm",
            ts_rank("searchVector", to_tsquery('portuguese', $1)) AS rank,
            ts_headline('portuguese', objeto, to_tsquery('portuguese', $1),
              'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=30') AS headline
     FROM "Licitacao"
     WHERE ${whereClause}
     ORDER BY ${effectiveOrderBy}
     LIMIT ${limitParam} OFFSET ${offsetParam}`,
    ...queryParams,
  );

  // Build highlights map and strip rank/headline from data
  const highlights: Record<string, string> = {};
  const data = rows.map(({ rank: _rank, headline, ...row }) => {
    if (headline && typeof headline === 'string') {
      highlights[row.id as string] = headline;
    }
    return row;
  });

  const totalPages = Math.ceil(total / params.pageSize);
  return {
    data,
    pagination: { page: params.page, pageSize: params.pageSize, total, totalPages },
    highlights,
  };
}
```

**Step 4: Run all backend tests to verify they pass**

Run: `cd backend && npx vitest run`
Expected: All tests PASS (existing + new).

**Step 5: Commit**

```bash
git add backend/src/api/routes/licitacoes.ts backend/tests/unit/licitacoes.test.ts
git commit -m "feat(search): integrate tsvector full-text search into GET /api/licitacoes"
```

---

### Task 4: Update frontend types for highlights

**Files:**
- Modify: `frontend/src/types/index.ts` (line 126-129)

**Step 1: Add highlights to PaginatedResponse**

In `frontend/src/types/index.ts`, change the `PaginatedResponse` interface (line 126):

```typescript
export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
  highlights?: Record<string, string>;
}
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(types): add highlights field to PaginatedResponse"
```

---

### Task 5: Update Zustand store to handle highlights

**Files:**
- Modify: `frontend/src/stores/search-store.ts`

**Step 1: Add highlights to the store state**

Modify `frontend/src/stores/search-store.ts`:

1. Add `highlights` to the `SearchState` interface (after line 7):
```typescript
  highlights: Record<string, string>;
```

2. Add to initial state (after line 26):
```typescript
  highlights: {},
```

3. Update the `search()` method to capture highlights (line 43-44):
```typescript
      const res = await licitacoes.list(filters);
      set({
        results: res.data,
        pagination: res.pagination,
        highlights: res.highlights ?? {},
        loading: false,
      });
```

4. Update `resetFilters` to clear highlights (line 36):
```typescript
    set({ filters: { ...DEFAULT_FILTERS }, highlights: {} });
```

5. Add auto-relevance: When `q` is set and `ordenarPor` is default, switch to relevance ordering.
   In `setFilters` (line 31-33), add logic:
```typescript
  setFilters(newFilters) {
    set((s) => {
      const merged = { ...s.filters, ...newFilters, page: 1 };
      // Auto-select relevance ordering when search text is present
      if (newFilters.q !== undefined) {
        merged.ordenarPor = newFilters.q ? 'relevancia' : 'dataPublicacao';
      }
      return { filters: merged };
    });
  },
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/stores/search-store.ts
git commit -m "feat(store): add highlights and auto-relevance ordering to search store"
```

---

### Task 6: Update LicitacaoCard to render highlighted snippets

**Files:**
- Modify: `frontend/src/components/search/LicitacaoCard.tsx`

**Step 1: Add highlight prop and rendering**

Modify `frontend/src/components/search/LicitacaoCard.tsx`:

1. Update the Props interface (line 8):
```typescript
interface Props {
  licitacao: Licitacao;
  highlight?: string;
}
```

2. Update the component signature (line 11):
```typescript
export function LicitacaoCard({ licitacao, highlight }: Props) {
```

3. Add a sanitize helper above the component:
```typescript
/**
 * Strip all HTML tags except <mark> and </mark> for safe dangerouslySetInnerHTML.
 */
function sanitizeHighlight(html: string): string {
  return html.replace(/<(?!\/?mark\b)[^>]*>/gi, '');
}
```

4. Replace the object description section (lines 33-37) with:
```typescript
      {/* Object description */}
      <Link to={`/licitacao/${l.id}`} className="block">
        {highlight ? (
          <h3
            className="mb-2 font-semibold leading-snug text-gray-900 group-hover:text-primary transition-colors dark:text-gray-100"
            dangerouslySetInnerHTML={{ __html: sanitizeHighlight(highlight) }}
          />
        ) : (
          <h3 className="mb-2 font-semibold leading-snug text-gray-900 group-hover:text-primary transition-colors dark:text-gray-100 line-clamp-2">
            {l.objeto}
          </h3>
        )}
      </Link>
```

**Step 2: Add mark tag styling to index.css**

In `frontend/src/index.css`, add after `body { ... }` (line 86):

```css
mark {
  background-color: hsl(48 100% 67%);
  color: inherit;
  padding: 0 2px;
  border-radius: 2px;
}

.dark mark {
  background-color: hsl(48 100% 30%);
}
```

**Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 4: Commit**

```bash
git add frontend/src/components/search/LicitacaoCard.tsx frontend/src/index.css
git commit -m "feat(ui): render search highlights in LicitacaoCard with sanitized HTML"
```

---

### Task 7: Wire highlights from store to card in ResultsList

**Files:**
- Modify: `frontend/src/components/search/ResultsList.tsx` (line 51-53)

**Step 1: Pass highlights to each card**

In `frontend/src/components/search/ResultsList.tsx`:

1. Add `highlights` to the store destructure (line 6):
```typescript
  const { results, pagination, loading, error, setPage, highlights } = useSearchStore();
```

Note: Need to also export `highlights` from the store — but it's already on the state object, so destructuring works. Actually, since we added it to `SearchState` in Task 5, it's already available.

2. Update the card rendering (lines 51-53):
```typescript
        {results.map((l) => (
          <LicitacaoCard key={l.id} licitacao={l} highlight={highlights[l.id]} />
        ))}
```

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/components/search/ResultsList.tsx
git commit -m "feat(ui): pass highlights from store to LicitacaoCard"
```

---

### Task 8: Add "Relevância" option to FilterPanel ordering

**Files:**
- Modify: `frontend/src/components/search/FilterPanel.tsx` (lines 125-135)

**Step 1: Add conditional Relevância option**

In `frontend/src/components/search/FilterPanel.tsx`, replace the ordering section (lines 124-135):

```typescript
      {/* Ordenação */}
      <FilterSection title="🔃 Ordenar por">
        <select
          value={filters.ordenarPor ?? 'dataPublicacao'}
          onChange={(e) => { setFilters({ ordenarPor: e.target.value as SearchFilters['ordenarPor'] }); apply(); }}
          className="w-full rounded-lg border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-800"
        >
          {filters.q && <option value="relevancia">Relevância</option>}
          <option value="dataPublicacao">Mais recentes</option>
          <option value="dataAbertura">Próxima abertura</option>
          <option value="valorEstimado">Maior valor</option>
        </select>
      </FilterSection>
```

The "Relevância" option only appears when there's a search query active.

**Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 3: Commit**

```bash
git add frontend/src/components/search/FilterPanel.tsx
git commit -m "feat(ui): show Relevância ordering option when search query is active"
```

---

### Task 9: Clean up the old /search endpoint

**Files:**
- Modify: `backend/src/api/routes/licitacoes.ts`
- Modify: `backend/tests/unit/licitacoes.test.ts`

**Step 1: Remove the standalone /search endpoint**

The `GET /api/licitacoes/search` endpoint is now redundant since full-text search is integrated into `GET /api/licitacoes`. Remove the `/search` route handler (lines 246-324 in the original file) and the `searchQuerySchema` (lines 67-71).

**Step 2: Update tests**

Remove the `describe('GET /api/licitacoes/search')` block from `licitacoes.test.ts` (lines 169-196).

**Step 3: Remove the unused `licitacoes.search()` method from the frontend API service**

In `frontend/src/services/api.ts`, remove (lines 126-128):
```typescript
  async search(q: string, page = 1): Promise<PaginatedResponse<Licitacao>> {
    return request(`/licitacoes/search?q=${encodeURIComponent(q)}&page=${page}`);
  },
```

**Step 4: Run all tests**

Run: `cd backend && npx vitest run`
Expected: All tests PASS.

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 5: Commit**

```bash
git add backend/src/api/routes/licitacoes.ts backend/tests/unit/licitacoes.test.ts frontend/src/services/api.ts
git commit -m "refactor: remove redundant /search endpoint, search is now unified in GET /api/licitacoes"
```

---

### Task 10: Run full test suite and verify in browser

**Step 1: Run all backend tests**

Run: `cd backend && npx vitest run`
Expected: All tests PASS.

**Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

**Step 3: Start backend and frontend**

Run: `cd backend && npm run dev` (in background)
Run: `cd frontend && npm run dev` (in background)

**Step 4: Browser verification checklist**

1. Navigate to search page
2. Type "saude" in search bar and submit
3. Verify: Results appear with highlighted `<mark>` tags in card titles
4. Verify: "Relevância" option appears in ordering dropdown
5. Verify: Pagination works with search
6. Apply a filter (e.g., esfera=FEDERAL) alongside search — verify both work together
7. Clear search term — verify "Relevância" option disappears, normal ordering returns
8. Verify dark mode: highlights visible with dark background
9. Search for "agua potavel" (with quotes) — verify phrase search works

**Step 5: Final commit (if any fixes needed)**

```bash
git add -A
git commit -m "fix: address issues found during browser verification"
```

---

## File Change Summary

| File | Action | Purpose |
|------|--------|---------|
| `backend/prisma/migrations/.../migration.sql` | Create | Trigger + backfill |
| `backend/src/lib/search-query.ts` | Create | Query sanitization |
| `backend/tests/unit/search-query.test.ts` | Create | Sanitization tests |
| `backend/src/api/routes/licitacoes.ts` | Modify | tsvector integration |
| `backend/tests/unit/licitacoes.test.ts` | Modify | New search tests |
| `frontend/src/types/index.ts` | Modify | Add highlights type |
| `frontend/src/stores/search-store.ts` | Modify | Store highlights |
| `frontend/src/components/search/LicitacaoCard.tsx` | Modify | Render highlights |
| `frontend/src/components/search/ResultsList.tsx` | Modify | Pass highlights |
| `frontend/src/components/search/FilterPanel.tsx` | Modify | Relevância option |
| `frontend/src/index.css` | Modify | Mark tag styling |
| `frontend/src/services/api.ts` | Modify | Remove old search |
