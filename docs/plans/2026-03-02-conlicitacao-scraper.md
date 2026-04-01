# ConLicitação Scraper Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add ConLicitação as a third data source, scraping licitações from their API at `consultaonline.conlicitacao.com.br`.

**Architecture:** ConLicitação is a Rails app with session-based auth (CSRF-protected). We use Puppeteer (already a dependency) to log in and extract the `_boletim_web_session` cookie, then use it with `fetch` for paginated API calls to `GET /biddings.json`. An `AuthManager` class handles cookie lifecycle. The scraper extends `BaseScraper` like the existing PNCP and Querido Diário scrapers.

**Tech Stack:** TypeScript, Puppeteer (existing dep), BaseScraper pattern, Vitest, BullMQ scheduler.

---

## API Details (discovered via exploration)

- **Base URL:** `https://consultaonline.conlicitacao.com.br` (note: 'a' not 'e')
- **Endpoint:** `GET /biddings.json?page=N&per_page=50&modified[from]=ISO&modified[to]=ISO`
- **Auth:** httpOnly `_boletim_web_session` cookie set after Puppeteer login at `/users/login`
- **Login page:** `https://consultaonline.conlicitacao.com.br/users/login` (empty HTML, session cookie set on GET)
- **Login POST:** `https://consultaonline.conlicitacao.com.br/users/login` with form data `user[email]=X&user[password]=Y` + CSRF token from session
- **Date filter:** `modified[from]=2026-03-01T00:00:00.000-03:00&modified[to]=2026-03-02T23:59:59.000-03:00`
- **Default (no filter):** 645,000+ entries; with 2-day window: ~400 entries
- **Response:**
```json
{
  "total_entries": 406,
  "total_pages": 9,
  "page": 1,
  "biddings": [{
    "id": 18675561,
    "orgao_uasg": "926483",
    "orgao_cidade": "Belo Horizonte",
    "orgao_estado": "MG",
    "edital": "PE/90012/2026",
    "edital_site": "https://pncp.gov.br/editais/...",
    "processo": "004001-09098",
    "valor_estimado": 0.0,
    "objeto": "Contratação de serviços...",
    "datahora_prazo": "2026-03-16T09:00:00.000-03:00",
    "datahora_abertura": null,
    "data_validade": "2026-03-16",
    "modified": "2026-03-02T09:28:47.000-03:00",
    "created": "2026-03-02T08:24:59.000-03:00",
    "public_body": { "nome": "SESC-MG" },
    "modality": { "nome": "Pregão Eletrônico" },
    "bidding_grouping": { "descricao": "NOVA" },
    "itens": "1 - Instalação / Remoção...",
    "observacao": "Unidade compradora: ...",
    "edicts": [{ "filename": "edital.zip", "url": "/boletim_web/public/licitacoes/18675561/arquivos/edital.zip" }]
  }]
}
```

---

### Task 1: Add environment variables

**Files:**
- Modify: `backend/src/config/env.ts`
- Modify: `backend/.env` (manually, not committed)

**Step 1: Add CONLICITACAO env vars to schema**

In `backend/src/config/env.ts`, add to `envSchema`:

```typescript
CONLICITACAO_EMAIL: z.string().default(''),
CONLICITACAO_PASSWORD: z.string().default(''),
CONLICITACAO_API_BASE: z.string().default('https://consultaonline.conlicitacao.com.br'),
```

**Step 2: Add values to .env**

```
CONLICITACAO_EMAIL=licitacao@argusbr.com
CONLICITACAO_PASSWORD=Arguss@2025
CONLICITACAO_API_BASE=https://consultaonline.conlicitacao.com.br
```

**Step 3: Verify TypeScript compiles**

Run: `node backend/node_modules/typescript/bin/tsc --noEmit -p backend/tsconfig.json`
Expected: exit 0, zero errors

**Step 4: Commit**

```bash
git add backend/src/config/env.ts
git commit -m "feat: add ConLicitação env vars"
```

---

### Task 2: Create ConLicitação auth manager

**Files:**
- Create: `backend/src/scrapers/agregadores/conlicitacao-auth.ts`
- Test: `backend/tests/unit/conlicitacao-auth.test.ts`

**Step 1: Write failing test for auth manager**

```typescript
// backend/tests/unit/conlicitacao-auth.test.ts
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const { mockLogger, mockChildLogger } = vi.hoisted(() => {
  const mockChildLogger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  };
  return {
    mockChildLogger,
    mockLogger: {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
      child: vi.fn().mockReturnValue(mockChildLogger),
    },
  };
});

vi.mock('../../src/lib/logger.js', () => ({
  logger: mockLogger,
}));

vi.mock('../../src/config/env.js', () => ({
  env: {
    CONLICITACAO_EMAIL: 'test@example.com',
    CONLICITACAO_PASSWORD: 'testpass',
    CONLICITACAO_API_BASE: 'https://consultaonline.conlicitacao.com.br',
    SCRAPING_RATE_LIMIT_MS: 0,
    DATABASE_URL: 'test',
    REDIS_URL: 'test',
    JWT_SECRET: 'test',
    JWT_REFRESH_SECRET: 'test',
    JWT_EXPIRES_IN: '15m',
    JWT_REFRESH_EXPIRES_IN: '7d',
    PORT: 3099,
    NODE_ENV: 'test',
    CORS_ORIGIN: '*',
    PNCP_API_BASE: 'test',
    QUERIDO_DIARIO_API_BASE: 'test',
    SCRAPING_CONCURRENCY: 1,
    LOG_LEVEL: 'silent',
  },
}));

import { ConLicitacaoAuth } from '../../src/scrapers/agregadores/conlicitacao-auth.js';

describe('ConLicitacaoAuth', () => {
  let auth: ConLicitacaoAuth;

  beforeEach(() => {
    vi.clearAllMocks();
    auth = new ConLicitacaoAuth();
  });

  it('starts with no cached cookie', () => {
    expect(auth.hasCachedSession()).toBe(false);
  });

  it('caches cookie after manual set', () => {
    auth.setSessionCookie('test_session_value');
    expect(auth.hasCachedSession()).toBe(true);
    expect(auth.getSessionCookie()).toBe('test_session_value');
  });

  it('clears cache', () => {
    auth.setSessionCookie('test_session_value');
    auth.clearSession();
    expect(auth.hasCachedSession()).toBe(false);
  });

  it('builds auth headers with cookie', () => {
    auth.setSessionCookie('abc123');
    const headers = auth.getAuthHeaders();
    expect(headers['Cookie']).toBe('_boletim_web_session=abc123');
    expect(headers['Accept']).toBe('application/json');
  });

  it('throws when getting headers without session', () => {
    expect(() => auth.getAuthHeaders()).toThrow('Not authenticated');
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd backend && npx vitest run tests/unit/conlicitacao-auth.test.ts`
Expected: FAIL — module not found

**Step 3: Implement ConLicitacaoAuth**

```typescript
// backend/src/scrapers/agregadores/conlicitacao-auth.ts
import puppeteer from 'puppeteer';
import { env } from '../../config/env.js';
import { logger as rootLogger } from '../../lib/logger.js';

const logger = rootLogger.child({ module: 'conlicitacao-auth' });

export class ConLicitacaoAuth {
  private sessionCookie: string | null = null;
  private lastAuthAt: Date | null = null;
  private readonly maxSessionAgeMs = 30 * 60 * 1000; // 30 min

  hasCachedSession(): boolean {
    if (!this.sessionCookie) return false;
    if (this.lastAuthAt && Date.now() - this.lastAuthAt.getTime() > this.maxSessionAgeMs) {
      this.sessionCookie = null;
      this.lastAuthAt = null;
      return false;
    }
    return true;
  }

  getSessionCookie(): string | null {
    return this.sessionCookie;
  }

  setSessionCookie(cookie: string): void {
    this.sessionCookie = cookie;
    this.lastAuthAt = new Date();
  }

  clearSession(): void {
    this.sessionCookie = null;
    this.lastAuthAt = null;
  }

  getAuthHeaders(): Record<string, string> {
    if (!this.sessionCookie) {
      throw new Error('Not authenticated — call authenticate() first');
    }
    return {
      'Cookie': `_boletim_web_session=${this.sessionCookie}`,
      'Accept': 'application/json',
      'User-Agent': 'LicitaBrasil/1.0',
    };
  }

  /**
   * Log in via Puppeteer to obtain the httpOnly _boletim_web_session cookie.
   * The Rails app has CSRF protection, so we must use a real browser.
   */
  async authenticate(): Promise<void> {
    if (this.hasCachedSession()) {
      logger.debug('Using cached ConLicitação session');
      return;
    }

    logger.info('Authenticating with ConLicitação via Puppeteer');
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    try {
      const page = await browser.newPage();

      // Navigate to login page to get session cookie + CSRF
      await page.goto(`${env.CONLICITACAO_API_BASE}/users/login`, {
        waitUntil: 'networkidle2',
        timeout: 30_000,
      });

      // Fill login form and submit
      await page.evaluate(
        (email, password) => {
          // The login page may render a Devise form or the React SPA handles it
          // We POST directly via fetch inside the page context (has CSRF cookie)
          return fetch('/users/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `user[email]=${encodeURIComponent(email)}&user[password]=${encodeURIComponent(password)}`,
            credentials: 'same-origin',
            redirect: 'manual',
          }).then((r) => r.status);
        },
        env.CONLICITACAO_EMAIL,
        env.CONLICITACAO_PASSWORD,
      );

      // Extract the session cookie
      const cookies = await page.cookies();
      const sessionCookie = cookies.find((c) => c.name === '_boletim_web_session');

      if (!sessionCookie) {
        throw new Error('Login failed — _boletim_web_session cookie not found');
      }

      this.setSessionCookie(sessionCookie.value);
      logger.info('ConLicitação authentication successful');
    } finally {
      await browser.close();
    }
  }
}
```

**Step 4: Run test to verify it passes**

Run: `cd backend && npx vitest run tests/unit/conlicitacao-auth.test.ts`
Expected: 5 tests PASS

**Step 5: Commit**

```bash
git add backend/src/scrapers/agregadores/conlicitacao-auth.ts backend/tests/unit/conlicitacao-auth.test.ts
git commit -m "feat: add ConLicitação auth manager with Puppeteer login"
```

---

### Task 3: Create ConLicitação scraper

**Files:**
- Create: `backend/src/scrapers/agregadores/conlicitacao-scraper.ts`
- Test: `backend/tests/unit/conlicitacao-scraper.test.ts`

**Step 1: Write failing test for data mapping**

```typescript
// backend/tests/unit/conlicitacao-scraper.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockLogger, mockChildLogger } = vi.hoisted(() => {
  const mockChildLogger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  };
  return {
    mockChildLogger,
    mockLogger: {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
      child: vi.fn().mockReturnValue(mockChildLogger),
    },
  };
});

vi.mock('../../src/lib/prisma.js', () => ({
  prisma: {
    fonteDados: {
      upsert: vi.fn().mockResolvedValue({}),
      update: vi.fn().mockResolvedValue({}),
    },
    licitacao: {
      findUnique: vi.fn().mockResolvedValue(null),
      create: vi.fn().mockResolvedValue({ id: 'test-id' }),
      update: vi.fn().mockResolvedValue({ id: 'test-id' }),
    },
  },
}));

vi.mock('../../src/lib/logger.js', () => ({
  logger: mockLogger,
}));

vi.mock('../../src/config/env.js', () => ({
  env: {
    CONLICITACAO_EMAIL: 'test@example.com',
    CONLICITACAO_PASSWORD: 'testpass',
    CONLICITACAO_API_BASE: 'https://consultaonline.conlicitacao.com.br',
    SCRAPING_RATE_LIMIT_MS: 0,
    DATABASE_URL: 'test',
    REDIS_URL: 'test',
    JWT_SECRET: 'test',
    JWT_REFRESH_SECRET: 'test',
    JWT_EXPIRES_IN: '15m',
    JWT_REFRESH_EXPIRES_IN: '7d',
    PORT: 3099,
    NODE_ENV: 'test',
    CORS_ORIGIN: '*',
    PNCP_API_BASE: 'test',
    QUERIDO_DIARIO_API_BASE: 'test',
    SCRAPING_CONCURRENCY: 1,
    LOG_LEVEL: 'silent',
  },
}));

vi.mock('@prisma/client', () => ({
  Prisma: {
    Decimal: class Decimal {
      constructor(public value: number) {}
      toString() { return String(this.value); }
    },
  },
  Modalidade: {
    PREGAO_ELETRONICO: 'PREGAO_ELETRONICO',
    PREGAO_PRESENCIAL: 'PREGAO_PRESENCIAL',
    CONCORRENCIA: 'CONCORRENCIA',
    CONCORRENCIA_ELETRONICA: 'CONCORRENCIA_ELETRONICA',
    TOMADA_DE_PRECOS: 'TOMADA_DE_PRECOS',
    CONVITE: 'CONVITE',
    CONCURSO: 'CONCURSO',
    LEILAO: 'LEILAO',
    DIALOGO_COMPETITIVO: 'DIALOGO_COMPETITIVO',
    DISPENSA: 'DISPENSA',
    INEXIGIBILIDADE: 'INEXIGIBILIDADE',
    CREDENCIAMENTO: 'CREDENCIAMENTO',
    RDC: 'RDC',
    OUTRA: 'OUTRA',
  },
  Esfera: {
    FEDERAL: 'FEDERAL',
    ESTADUAL: 'ESTADUAL',
    MUNICIPAL: 'MUNICIPAL',
  },
  StatusLicitacao: {
    PUBLICADA: 'PUBLICADA',
    ABERTA: 'ABERTA',
    EM_ANDAMENTO: 'EM_ANDAMENTO',
    SUSPENSA: 'SUSPENSA',
    ADIADA: 'ADIADA',
    ENCERRADA: 'ENCERRADA',
    ANULADA: 'ANULADA',
    REVOGADA: 'REVOGADA',
    DESERTA: 'DESERTA',
    FRACASSADA: 'FRACASSADA',
    HOMOLOGADA: 'HOMOLOGADA',
    ADJUDICADA: 'ADJUDICADA',
  },
  TipoLicitacao: {
    COMPRA: 'COMPRA',
    SERVICO: 'SERVICO',
    OBRA: 'OBRA',
    SERVICO_ENGENHARIA: 'SERVICO_ENGENHARIA',
    ALIENACAO: 'ALIENACAO',
    CONCESSAO: 'CONCESSAO',
    PERMISSAO: 'PERMISSAO',
    LOCACAO: 'LOCACAO',
    OUTRO: 'OUTRO',
  },
}));

// Mock the auth manager — avoid real Puppeteer in tests
vi.mock('../../src/scrapers/agregadores/conlicitacao-auth.js', () => ({
  ConLicitacaoAuth: class {
    hasCachedSession() { return true; }
    getSessionCookie() { return 'test_session'; }
    setSessionCookie() {}
    clearSession() {}
    getAuthHeaders() {
      return {
        Cookie: '_boletim_web_session=test_session',
        Accept: 'application/json',
        'User-Agent': 'LicitaBrasil/1.0',
      };
    }
    async authenticate() {}
  },
}));

import { ConLicitacaoScraper } from '../../src/scrapers/agregadores/conlicitacao-scraper.js';

// Mock fetch
const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function makeBidding(overrides: Record<string, unknown> = {}) {
  return {
    id: 18675561,
    orgao_uasg: '926483',
    orgao_endereco: 'Rua Tupinambás, 1038',
    orgao_cidade: 'Belo Horizonte',
    orgao_estado: 'MG',
    orgao_cep: '30120-070',
    edital: 'PE/90012/2026',
    edital_site: 'https://pncp.gov.br/editais/12345',
    edital_tem: true,
    processo: '004001-09098',
    valor_estimado: 150000.50,
    itens: '1 - Instalação de equipamentos',
    datahora_prazo: '2026-03-16T09:00:00.000-03:00',
    datahora_abertura: null,
    data_validade: '2026-03-16',
    objeto: 'Contratação de serviços de manutenção predial',
    observacao: 'Unidade compradora: Sesc MG',
    modified: '2026-03-02T09:28:47.000-03:00',
    created: '2026-03-02T08:24:59.000-03:00',
    fonte_id: 6660,
    edicts: [{ filename: 'edital.zip', url: '/boletim_web/public/licitacoes/18675561/arquivos/edital.zip' }],
    has_electronic_trading: true,
    electronic_trading: { trading_id: '03643856000173/2026/10' },
    public_body: { id: 7384, nome: 'SESC-Serviço Social do Comércio de Minas Gerais', tipo_orgao_id: 3 },
    modality: { nome: 'Pregão Eletrônico' },
    bidding_grouping: { descricao: 'NOVA' },
    contracts: [],
    ...overrides,
  };
}

function makeApiResponse(biddings: unknown[], total_entries = biddings.length, total_pages = 1, page = 1) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({ total_entries, total_pages, page, biddings }),
    text: () => Promise.resolve(''),
  };
}

describe('ConLicitacaoScraper', () => {
  let scraper: ConLicitacaoScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new ConLicitacaoScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('CONLICITACAO');
    expect(scraper.getSourceUrl()).toBe('https://consultaonline.conlicitacao.com.br');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('fetchLicitacoes', () => {
    it('maps bidding to RawLicitacao correctly', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([makeBidding()]));

      const results = await scraper.fetchLicitacoes({ pageSize: 50 });

      expect(results).toHaveLength(1);
      const r = results[0];
      expect(r.fonteOrigem).toBe('CONLICITACAO');
      expect(r.orgao).toBe('SESC-Serviço Social do Comércio de Minas Gerais');
      expect(r.uf).toBe('MG');
      expect(r.municipio).toBe('Belo Horizonte');
      expect(r.numeroEdital).toBe('PE/90012/2026');
      expect(r.numeroProcesso).toBe('004001-09098');
      expect(r.objeto).toBe('Contratação de serviços de manutenção predial');
      expect(r.valorEstimado).toBe(150000.50);
      expect(r.modalidade).toBe('Pregão Eletrônico');
      expect(r.dataPublicacao).toBe('2026-03-02T08:24:59.000-03:00');
      expect(r.dataAbertura).toBeNull();
      expect(r.dataEncerramento).toBe('2026-03-16T09:00:00.000-03:00');
      expect(r.urlEdital).toBe('https://pncp.gov.br/editais/12345');
      expect(r.urlOrigem).toBe('https://consultaonline.conlicitacao.com.br/boletim_web/public/licitacoes/18675561');
      expect(r.status).toBe('publicada');
    });

    it('uses modified[from]/[to] date filter params', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([]));

      await scraper.fetchLicitacoes({ dataInicio: '2026-03-01', dataFim: '2026-03-02' });

      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain('modified%5Bfrom%5D=');
      expect(url).toContain('modified%5Bto%5D=');
      expect(url).toContain('2026-03-01');
      expect(url).toContain('2026-03-02');
    });

    it('handles empty response', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([]));

      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(0);
    });

    it('paginates through multiple pages', async () => {
      const page1 = Array.from({ length: 50 }, (_, i) =>
        makeBidding({ id: i + 1, edital: `ED-${i + 1}` }),
      );
      const page2 = [makeBidding({ id: 51, edital: 'ED-51' })];

      mockFetch
        .mockResolvedValueOnce(makeApiResponse(page1, 51, 2, 1))
        .mockResolvedValueOnce(makeApiResponse(page2, 51, 2, 2));

      const results = await scraper.fetchLicitacoes({ pageSize: 50 });

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(results).toHaveLength(51);
    });

    it('maps NOVA grouping to status publicada', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([
        makeBidding({ bidding_grouping: { descricao: 'NOVA' } }),
      ]));
      const results = await scraper.fetchLicitacoes({});
      expect(results[0].status).toBe('publicada');
    });

    it('maps bidding without edital_site to constructed URL', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([
        makeBidding({ edital_site: null, id: 999 }),
      ]));
      const results = await scraper.fetchLicitacoes({});
      expect(results[0].urlEdital).toBeNull();
    });

    it('maps bidding without public_body to fallback orgao', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([
        makeBidding({ public_body: null }),
      ]));
      const results = await scraper.fetchLicitacoes({});
      expect(results[0].orgao).toBe('Órgão não informado');
    });

    it('re-authenticates on 423 response', async () => {
      mockFetch
        .mockResolvedValueOnce({ ok: false, status: 423, text: () => Promise.resolve('Locked') })
        .mockResolvedValue(makeApiResponse([makeBidding()]));

      const results = await scraper.fetchLicitacoes({});
      // Should have retried after re-auth
      expect(results.length).toBeGreaterThanOrEqual(0);
    });
  });

  describe('run()', () => {
    it('returns ScrapingResult with correct counts', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([
        makeBidding({ id: 1, edital: 'A', objeto: 'Compra de material' }),
        makeBidding({ id: 2, edital: 'B', objeto: 'Serviço de limpeza' }),
      ]));

      const result = await scraper.run({ pageSize: 50 });

      expect(result.source).toBe('CONLICITACAO');
      expect(result.total).toBe(2);
      expect(result.created).toBe(2);
      expect(result.errors).toBe(0);
    });
  });
});
```

**Step 2: Run test to verify it fails**

Run: `cd backend && npx vitest run tests/unit/conlicitacao-scraper.test.ts`
Expected: FAIL — module not found

**Step 3: Implement ConLicitacaoScraper**

```typescript
// backend/src/scrapers/agregadores/conlicitacao-scraper.ts
import { Esfera } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';
import { ConLicitacaoAuth } from './conlicitacao-auth.js';
import { env } from '../../config/env.js';

// ---------------------------------------------------------------------------
// ConLicitação API response types
// ---------------------------------------------------------------------------

interface ConLicitBidding {
  id: number;
  orgao_uasg: string | null;
  orgao_endereco: string | null;
  orgao_cidade: string | null;
  orgao_estado: string | null;
  orgao_cep: string | null;
  edital: string | null;
  edital_site: string | null;
  edital_tem: boolean;
  processo: string | null;
  valor_estimado: number | null;
  itens: string | null;
  datahora_prazo: string | null;
  datahora_abertura: string | null;
  data_validade: string | null;
  objeto: string | null;
  observacao: string | null;
  modified: string;
  created: string;
  fonte_id: number | null;
  edicts: Array<{ filename: string; url: string }>;
  has_electronic_trading: boolean;
  electronic_trading: { trading_id?: string } | null;
  public_body: { id?: number; nome: string; tipo_orgao_id?: number } | null;
  modality: { nome: string } | null;
  bidding_grouping: { descricao: string } | null;
  contracts: unknown[];
}

interface ConLicitResponse {
  total_entries: number;
  total_pages: number;
  page: number;
  biddings: ConLicitBidding[];
}

// ---------------------------------------------------------------------------
// Status mapping from bidding_grouping.descricao
// ---------------------------------------------------------------------------

const GROUPING_STATUS_MAP: Record<string, string> = {
  'NOVA': 'publicada',
  'ATUALIZADA': 'publicada',
  'VIGENTE': 'aberta',
  'ENCERRADA': 'encerrada',
  'SUSPENSA': 'suspensa',
  'ANULADA': 'anulada',
  'REVOGADA': 'revogada',
  'DESERTA': 'deserta',
  'FRACASSADA': 'fracassada',
  'HOMOLOGADA': 'homologada',
};

// ---------------------------------------------------------------------------
// ConLicitação Scraper
// ---------------------------------------------------------------------------

export class ConLicitacaoScraper extends BaseScraper {
  private readonly baseUrl: string;
  private readonly auth: ConLicitacaoAuth;

  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 2000); // 2s default — be respectful
    this.baseUrl = env.CONLICITACAO_API_BASE;
    this.auth = new ConLicitacaoAuth();
  }

  getName(): string {
    return 'CONLICITACAO';
  }

  getSourceUrl(): string {
    return 'https://consultaonline.conlicitacao.com.br';
  }

  getEsfera(): Esfera {
    // ConLicitação aggregates all esferas; default to FEDERAL,
    // but we'll infer per-item from the data when possible
    return Esfera.FEDERAL;
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    await this.auth.authenticate();

    const results: RawLicitacao[] = [];
    const perPage = Math.min(params.pageSize ?? 50, 50);

    // Default: last 24 hours
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const dataInicio = params.dataInicio ?? yesterday.toISOString().split('T')[0];
    const dataFim = params.dataFim ?? now.toISOString().split('T')[0];

    let page = params.page ?? 1;
    let hasMore = true;

    this.logger.info({ dataInicio, dataFim, perPage }, 'Fetching licitacoes from ConLicitação');

    while (hasMore) {
      const url = this.buildUrl(dataInicio, dataFim, page, perPage);
      this.logger.debug({ url, page }, 'Requesting ConLicitação page');

      let response: ConLicitResponse;
      try {
        response = await this.withRetry(async () => {
          const res = await fetch(url, { headers: this.auth.getAuthHeaders() });

          // Re-authenticate on session expiry
          if (res.status === 423 || res.status === 302) {
            this.logger.warn({ status: res.status }, 'Session expired, re-authenticating');
            this.auth.clearSession();
            await this.auth.authenticate();
            // Retry with new session
            const retry = await fetch(url, { headers: this.auth.getAuthHeaders() });
            if (!retry.ok) {
              throw new Error(`ConLicitação API returned ${retry.status} after re-auth`);
            }
            return retry.json() as Promise<ConLicitResponse>;
          }

          if (!res.ok) {
            const body = await res.text().catch(() => '');
            throw new Error(`ConLicitação API returned ${res.status}: ${body.slice(0, 200)}`);
          }

          return res.json() as Promise<ConLicitResponse>;
        }, `ConLicitação page=${page}`);
      } catch (err) {
        this.logger.error({ err, page }, 'Failed to fetch ConLicitação page');
        break;
      }

      if (!response.biddings || response.biddings.length === 0) {
        hasMore = false;
        break;
      }

      for (const bidding of response.biddings) {
        try {
          results.push(this.mapToRawLicitacao(bidding));
        } catch (err) {
          this.logger.warn({ err, biddingId: bidding.id }, 'Failed to map ConLicitação bidding');
        }
      }

      this.logger.info(
        { page, items: response.biddings.length, totalSoFar: results.length, totalEntries: response.total_entries },
        'ConLicitação page fetched',
      );

      if (page >= response.total_pages) {
        hasMore = false;
      } else {
        page++;
        await this.rateLimit();
      }
    }

    this.logger.info({ total: results.length }, 'ConLicitação fetch complete');
    return results;
  }

  // ---- Private helpers ----

  private buildUrl(dataInicio: string, dataFim: string, page: number, perPage: number): string {
    const from = `${dataInicio}T00:00:00.000-03:00`;
    const to = `${dataFim}T23:59:59.000-03:00`;

    const searchParams = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      'modified[from]': from,
      'modified[to]': to,
    });

    return `${this.baseUrl}/biddings.json?${searchParams.toString()}`;
  }

  private mapToRawLicitacao(b: ConLicitBidding): RawLicitacao {
    const orgao = b.public_body?.nome ?? 'Órgão não informado';
    const modalidade = b.modality?.nome ?? 'Outra';
    const status = GROUPING_STATUS_MAP[b.bidding_grouping?.descricao ?? ''] ?? 'publicada';

    return {
      numeroEdital: b.edital ?? null,
      numeroProcesso: b.processo ?? null,
      codigoUASG: b.orgao_uasg ?? null,
      codigoPNCP: null,
      modalidade,
      tipo: this.inferTipo(b.objeto ?? ''),
      natureza: null,
      regime: null,
      criterioJulgamento: null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: 'FEDERAL', // inferred at normalization step
      uf: b.orgao_estado ?? null,
      municipio: b.orgao_cidade ?? null,
      objeto: b.objeto ?? 'Objeto não informado',
      objetoResumido: (b.objeto ?? '').slice(0, 200),
      valorEstimado: b.valor_estimado && b.valor_estimado > 0 ? b.valor_estimado : null,
      valorMinimo: null,
      valorMaximo: null,
      dataPublicacao: b.created,
      dataAbertura: b.datahora_abertura ?? null,
      dataEncerramento: b.datahora_prazo ?? null,
      dataResultado: null,
      segmento: null,
      cnae: [],
      palavrasChave: this.extractKeywords(b.objeto ?? ''),
      urlEdital: b.edital_site ?? null,
      urlAnexos: b.edicts?.map((e) => `${this.baseUrl}${e.url}`) ?? [],
      status,
      situacao: b.bidding_grouping?.descricao ?? null,
      fonteOrigem: 'CONLICITACAO',
      urlOrigem: `${this.baseUrl}/boletim_web/public/licitacoes/${b.id}`,
    };
  }

  private inferTipo(objeto: string): string {
    if (!objeto) return 'outro';
    const lower = objeto.toLowerCase();
    if (lower.includes('obra') || lower.includes('construção') || lower.includes('reforma')) return 'obra';
    if (lower.includes('engenharia')) return 'serviço de engenharia';
    if (lower.includes('serviço') || lower.includes('servico') || lower.includes('prestação')) return 'serviço';
    if (lower.includes('locação') || lower.includes('locacao') || lower.includes('aluguel')) return 'locação';
    if (lower.includes('alienação') || lower.includes('alienacao') || lower.includes('venda')) return 'alienação';
    if (lower.includes('concessão') || lower.includes('concessao')) return 'concessão';
    return 'compra';
  }

  private extractSigla(name: string): string {
    const words = name.split(/\s+/).filter((w) => w.length > 2);
    const sigla = words.map((w) => w[0]).join('').toUpperCase().slice(0, 10);
    return sigla || name.slice(0, 10).toUpperCase();
  }

  private extractKeywords(texto: string): string[] {
    const stopwords = new Set([
      'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'sem', 'por', 'em',
      'que', 'uma', 'um', 'os', 'as', 'no', 'na', 'nos', 'nas', 'ao',
      'ou', 'e', 'a', 'o', 'se', 'não', 'mais', 'como', 'mas', 'foi',
      'ser', 'está', 'são', 'ter', 'sua', 'seu', 'seus', 'suas',
    ]);

    return texto
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, ' ')
      .split(/\s+/)
      .filter((w) => w.length > 2 && !stopwords.has(w))
      .filter((w, i, arr) => arr.indexOf(w) === i)
      .slice(0, 20);
  }
}
```

**Step 4: Run tests to verify they pass**

Run: `cd backend && npx vitest run tests/unit/conlicitacao-scraper.test.ts`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add backend/src/scrapers/agregadores/conlicitacao-scraper.ts backend/tests/unit/conlicitacao-scraper.test.ts
git commit -m "feat: add ConLicitação scraper with data mapping and pagination"
```

---

### Task 4: Register scraper in worker and scheduler

**Files:**
- Modify: `backend/src/jobs/worker.ts`
- Modify: `backend/src/scrapers/scheduler.ts`

**Step 1: Add ConLicitação to scraperFactory in worker.ts**

Add import and registry entry:

```typescript
// Add import at top
import { ConLicitacaoScraper } from '../scrapers/agregadores/conlicitacao-scraper.js';

// Add to scraperFactory
const scraperFactory: Record<string, () => PNCPScraper | QueridoDiarioScraper | ConLicitacaoScraper> = {
  pncp: () => new PNCPScraper(),
  PNCP: () => new PNCPScraper(),
  'querido-diario': () => new QueridoDiarioScraper(),
  QUERIDO_DIARIO: () => new QueridoDiarioScraper(),
  conlicitacao: () => new ConLicitacaoScraper(),
  CONLICITACAO: () => new ConLicitacaoScraper(),
};
```

**Step 2: Add ConLicitação cron schedule in scheduler.ts**

Add after the Querido Diário schedule:

```typescript
// ConLicitação — every 2 hours (aggregator, less frequent than primary sources)
cron.schedule('0 */2 * * *', async () => {
  logger.info('Cron: scheduling ConLicitação scraping');
  await scheduleScrapingJob('conlicitacao', { pageSize: 50 });
});
```

**Step 3: Verify TypeScript compiles**

Run: `node backend/node_modules/typescript/bin/tsc --noEmit -p backend/tsconfig.json`
Expected: exit 0, zero errors

**Step 4: Run all tests**

Run: `cd backend && npx vitest run`
Expected: all tests PASS

**Step 5: Commit**

```bash
git add backend/src/jobs/worker.ts backend/src/scrapers/scheduler.ts
git commit -m "feat: register ConLicitação scraper in worker and scheduler"
```

---

### Task 5: Integration smoke test

**Step 1: Start services**

Ensure PostgreSQL, Redis, and backend are running.

**Step 2: Run a manual scraping test**

Create a quick script or use the REPL to test:

```bash
cd backend && npx tsx -e "
import { ConLicitacaoScraper } from './src/scrapers/agregadores/conlicitacao-scraper.js';

const scraper = new ConLicitacaoScraper(0);
const results = await scraper.fetchLicitacoes({
  dataInicio: '2026-03-01',
  dataFim: '2026-03-02',
  pageSize: 5,
});
console.log('Fetched:', results.length, 'items');
if (results.length > 0) {
  console.log('Sample:', JSON.stringify(results[0], null, 2));
}
process.exit(0);
"
```

Expected: Puppeteer launches, authenticates, fetches ~400 items (limited to first page of 5 by pageSize), logs them.

**Step 3: Verify it saved to database (optional full run)**

```bash
cd backend && npx tsx -e "
import { ConLicitacaoScraper } from './src/scrapers/agregadores/conlicitacao-scraper.js';

const scraper = new ConLicitacaoScraper(500);
const result = await scraper.run({
  dataInicio: '2026-03-01',
  dataFim: '2026-03-02',
  pageSize: 50,
});
console.log('Result:', result);
process.exit(0);
"
```

Expected: `{ source: 'CONLICITACAO', total: ~400, created: ~400, updated: 0, errors: 0 }`

**Step 4: Final commit with any fixes**

```bash
git add -A
git commit -m "feat: complete ConLicitação scraper integration"
```
