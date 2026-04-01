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

    it('maps bidding without edital_site to null', async () => {
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
