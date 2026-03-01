import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * Unit tests for PNCPScraper.
 *
 * We mock the global fetch() to simulate PNCP API responses, and mock
 * Prisma to avoid real database access.
 */

// ---------------------------------------------------------------------------
// Mocks — use vi.hoisted() for logger so child() return value persists
// across tests even after vi.clearAllMocks()
// ---------------------------------------------------------------------------

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
    PNCP_API_BASE: 'https://pncp.gov.br/api/consulta',
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

import { PNCPScraper } from '../../src/scrapers/federal/pncp-scraper.js';

// ---------------------------------------------------------------------------
// Mock fetch
// ---------------------------------------------------------------------------

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function makePNCPResponse(items: unknown[], totalPaginas = 1) {
  return {
    ok: true,
    json: () => Promise.resolve({
      data: items,
      totalRegistros: items.length,
      totalPaginas,
      paginaAtual: 1,
    }),
    text: () => Promise.resolve(''),
  };
}

function makePNCPItem(overrides: Record<string, unknown> = {}) {
  return {
    numeroControlePNCP: '00000000-0001-2025',
    orgaoEntidade: {
      cnpj: '00000000000100',
      razaoSocial: 'Universidade Federal de Teste',
      poderId: 'E',
      esferaId: 'F',
    },
    unidadeOrgao: {
      ufSigla: 'DF',
      ufNome: 'Distrito Federal',
      municipioNome: 'Brasília',
      nomeUnidade: 'Universidade Federal de Teste',
      codigoIbge: '5300108',
    },
    modalidadeId: 6, // Pregão Eletrônico
    objetoCompra: 'Aquisição de material de escritório para atender demandas administrativas',
    valorTotalEstimado: 50000,
    dataPublicacaoPncp: '2025-01-20',
    dataAberturaProposta: '2025-02-05T10:00:00',
    situacaoCompraId: 2, // Aberta
    situacaoCompraNome: 'Aberta',
    amparoLegal: { codigo: 1, nome: 'Lei 14.133/2021, Art. 28, I', descricao: 'pregão' },
    linkSistemaOrigem: 'https://compras.gov.br/1',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('PNCPScraper', () => {
  let scraper: PNCPScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    // Re-assign fetch after clearAllMocks to ensure tracking works
    globalThis.fetch = mockFetch;
    scraper = new PNCPScraper(0); // no rate limit
  });

  it('has correct name and esfera', () => {
    expect(scraper.getName()).toBe('PNCP');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('fetchLicitacoes', () => {
    it('fetches and maps items correctly', async () => {
      const item = makePNCPItem();
      mockFetch.mockResolvedValue(makePNCPResponse([item]));

      const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });

      expect(results).toHaveLength(1);
      expect(results[0].fonteOrigem).toBe('PNCP');
      expect(results[0].orgao).toBe('Universidade Federal de Teste');
      expect(results[0].uf).toBe('DF');
      expect(results[0].municipio).toBe('Brasília');
      expect(results[0].esfera).toBe('FEDERAL');
      expect(results[0].natureza).toBe('Lei 14.133/2021, Art. 28, I');
      expect(results[0].valorEstimado).toBe(50000);
      expect(results[0].status).toBe('aberta');
      expect(results[0].codigoPNCP).toBe('00000000-0001-2025');
    });

    it('handles empty API response', async () => {
      mockFetch.mockResolvedValue(makePNCPResponse([]));

      const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
      expect(results).toHaveLength(0);
    });

    it('paginates until all pages are fetched', async () => {
      // Generate 10 items for page 1 (matching pageSize=10 so pagination continues)
      const page1Items = Array.from({ length: 10 }, (_, i) =>
        makePNCPItem({ numeroControlePNCP: `PNCP-${String(i + 1).padStart(3, '0')}` }),
      );
      const page2Items = [makePNCPItem({ numeroControlePNCP: 'PNCP-011' })];

      mockFetch
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            data: page1Items,
            totalPaginas: 2,
            paginaAtual: 1,
          }),
          text: () => Promise.resolve(''),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve({
            data: page2Items,
            totalPaginas: 2,
            paginaAtual: 2,
          }),
          text: () => Promise.resolve(''),
        });

      const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(results).toHaveLength(11);
    });

    it('retries on fetch failure', async () => {
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValue(makePNCPResponse([makePNCPItem()]));

      const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
      expect(results).toHaveLength(1);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('skips modalidade after max retries on persistent failure', async () => {
      mockFetch.mockResolvedValue({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Internal Server Error'),
      });

      // New behavior: fetchLicitacoes catches per-modalidade errors and skips
      const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
      expect(results).toHaveLength(0);
      // 3 retries (withRetry attempts) for the single modalidade
      expect(mockFetch).toHaveBeenCalledTimes(3);
    });

    it('maps modalidadeId correctly', async () => {
      const cases = [
        { modalidadeId: 6, expected: 'PREGAO_ELETRONICO' },
        { modalidadeId: 7, expected: 'PREGAO_PRESENCIAL' },
        { modalidadeId: 4, expected: 'CONCORRENCIA_ELETRONICA' },
        { modalidadeId: 8, expected: 'DISPENSA' },
        { modalidadeId: 9, expected: 'INEXIGIBILIDADE' },
        { modalidadeId: 999, expected: 'OUTRA' },
      ];

      for (const { modalidadeId, expected } of cases) {
        mockFetch.mockResolvedValue(makePNCPResponse([
          makePNCPItem({ modalidadeId }),
        ]));

        const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: modalidadeId });
        // modalidade is the string representation of the enum
        expect(results[0].modalidade).toBe(expected);
      }
    });

    it('infers tipo from objeto text', async () => {
      const tests = [
        { objeto: 'Construção de escola pública', expectedType: 'obra' },
        { objeto: 'Prestação de serviço de limpeza', expectedType: 'serviço' },
        { objeto: 'Aquisição de computadores', expectedType: 'compra' },
        { objeto: 'Serviço de engenharia civil', expectedType: 'serviço de engenharia' },
        { objeto: 'Locação de veículos', expectedType: 'locação' },
      ];

      for (const { objeto, expectedType } of tests) {
        mockFetch.mockResolvedValue(makePNCPResponse([
          makePNCPItem({ objetoCompra: objeto }),
        ]));

        const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
        expect(results[0].tipo).toBe(expectedType);
      }
    });

    it('extracts keywords from objeto', async () => {
      mockFetch.mockResolvedValue(makePNCPResponse([
        makePNCPItem({ objetoCompra: 'Aquisição de equipamentos hospitalares para UTI neonatal' }),
      ]));

      const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
      const kw = results[0].palavrasChave;
      expect(kw).toContain('aquisição');
      expect(kw).toContain('equipamentos');
      expect(kw).toContain('hospitalares');
      expect(kw).toContain('neonatal');
      // Stopwords should be excluded
      expect(kw).not.toContain('de');
      expect(kw).not.toContain('para');
    });

    it('maps situacaoCompraId to status', async () => {
      const statusCases = [
        { situacaoCompraId: 1, expected: 'publicada' },
        { situacaoCompraId: 4, expected: 'encerrada' },
        { situacaoCompraId: 8, expected: 'homologada' },
      ];

      for (const { situacaoCompraId, expected } of statusCases) {
        mockFetch.mockResolvedValue(makePNCPResponse([
          makePNCPItem({ situacaoCompraId, situacaoCompraNome: undefined }),
        ]));

        const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
        expect(results[0].status).toBe(expected);
      }
    });

    it('maps esferaId correctly', async () => {
      const esfCases = [
        { esferaId: 'F', expected: 'FEDERAL' },
        { esferaId: 'E', expected: 'ESTADUAL' },
        { esferaId: 'M', expected: 'MUNICIPAL' },
      ];

      for (const { esferaId, expected } of esfCases) {
        mockFetch.mockResolvedValue(makePNCPResponse([
          makePNCPItem({ orgaoEntidade: { cnpj: '00000000000100', razaoSocial: 'Teste', esferaId } }),
        ]));

        const results = await scraper.fetchLicitacoes({ pageSize: 10, codigoModalidadeContratacao: 6 });
        expect(results[0].esfera).toBe(expected);
      }
    });
  });

  describe('run()', () => {
    it('returns a ScrapingResult with correct counts', async () => {
      mockFetch.mockResolvedValue(makePNCPResponse([
        makePNCPItem({ numeroControlePNCP: 'A', objetoCompra: 'Aquisição de computadores para escritório' }),
        makePNCPItem({ numeroControlePNCP: 'B', objetoCompra: 'Contratação de serviço de limpeza predial' }),
      ]));

      const result = await scraper.run({ pageSize: 10, codigoModalidadeContratacao: 6 });

      expect(result.source).toBe('PNCP');
      expect(result.total).toBe(2);
      expect(result.created).toBe(2);
      expect(result.errors).toBe(0);
    });
  });
});
