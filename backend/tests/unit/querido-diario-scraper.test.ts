import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * Unit tests for QueridoDiarioScraper.
 *
 * Mocks global fetch() to simulate the Querido Diário API and mocks Prisma /
 * logger / env so no real DB or network is touched. Mirrors the setup used in
 * pncp-scraper.test.ts.
 */

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

vi.mock('../../src/lib/logger.js', () => ({ logger: mockLogger }));

vi.mock('../../src/config/env.js', () => ({
  env: {
    PNCP_API_BASE: 'test',
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
    QUERIDO_DIARIO_API_BASE: 'https://queridodiario.ok.org.br/api',
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
  Esfera: { FEDERAL: 'FEDERAL', ESTADUAL: 'ESTADUAL', MUNICIPAL: 'MUNICIPAL' },
  StatusLicitacao: {
    PUBLICADA: 'PUBLICADA', ABERTA: 'ABERTA', EM_ANDAMENTO: 'EM_ANDAMENTO',
    SUSPENSA: 'SUSPENSA', ADIADA: 'ADIADA', ENCERRADA: 'ENCERRADA',
    ANULADA: 'ANULADA', REVOGADA: 'REVOGADA', DESERTA: 'DESERTA',
    FRACASSADA: 'FRACASSADA', HOMOLOGADA: 'HOMOLOGADA', ADJUDICADA: 'ADJUDICADA',
  },
  TipoLicitacao: {
    COMPRA: 'COMPRA', SERVICO: 'SERVICO', OBRA: 'OBRA',
    SERVICO_ENGENHARIA: 'SERVICO_ENGENHARIA', ALIENACAO: 'ALIENACAO',
    CONCESSAO: 'CONCESSAO', PERMISSAO: 'PERMISSAO', LOCACAO: 'LOCACAO', OUTRO: 'OUTRO',
  },
}));

import { QueridoDiarioScraper } from '../../src/scrapers/municipal/querido-diario.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function makeQDResponse(gazettes: unknown[], total?: number) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({
      total_gazettes: total ?? gazettes.length,
      gazettes,
    }),
    text: () => Promise.resolve(''),
  };
}

function makeGazette(overrides: Record<string, unknown> = {}) {
  return {
    territory_id: '2611606',
    territory_name: 'Recife',
    state_code: 'PE',
    date: '2026-06-20',
    is_extra_edition: false,
    url: 'https://queridodiario.ok.org.br/recife/2026-06-20.pdf',
    excerpts: [
      'Pregão Eletrônico nº 012/2026 para aquisição de material de escritório. ' +
      'Valor estimado R$ 150.000,00. Abertura dia 30/06/2026.',
    ],
    ...overrides,
  };
}

describe('QueridoDiarioScraper', () => {
  let scraper: QueridoDiarioScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new QueridoDiarioScraper(0);
  });

  it('has correct name and esfera', () => {
    expect(scraper.getName()).toBe('QUERIDO_DIARIO');
    expect(scraper.getEsfera()).toBe('MUNICIPAL');
  });

  describe('fetchLicitacoes', () => {
    it('extracts a licitacao from a keyword-bearing excerpt', async () => {
      mockFetch.mockResolvedValue(makeQDResponse([makeGazette()]));

      const results = await scraper.fetchLicitacoes({ size: 10 });

      expect(results).toHaveLength(1);
      const r = results[0];
      expect(r.fonteOrigem).toBe('QUERIDO_DIARIO');
      expect(r.esfera).toBe('MUNICIPAL');
      expect(r.uf).toBe('PE');
      expect(r.municipio).toBe('Recife');
      expect(r.modalidade).toBe('PREGAO_ELETRONICO');
      expect(r.numeroEdital).toBe('012/2026');
      expect(r.valorEstimado).toBe(150000);
      expect(r.urlOrigem).toBe('https://queridodiario.ok.org.br/recife/2026-06-20.pdf');
    });

    it('falls back to a single OUTRA entry when no excerpt has a keyword', async () => {
      const gazette = makeGazette({
        excerpts: ['Nomeação de servidores e atos administrativos diversos do município.'],
      });
      mockFetch.mockResolvedValue(makeQDResponse([gazette]));

      const results = await scraper.fetchLicitacoes({ size: 10 });

      expect(results).toHaveLength(1);
      expect(results[0].modalidade).toBe('OUTRA');
      expect(results[0].numeroEdital).toBeNull();
    });

    it('returns nothing for an empty gazette list', async () => {
      mockFetch.mockResolvedValue(makeQDResponse([]));
      const results = await scraper.fetchLicitacoes({ size: 10 });
      expect(results).toHaveLength(0);
    });

    it('produces one item per keyword-bearing excerpt', async () => {
      const gazette = makeGazette({
        excerpts: [
          'Pregão Eletrônico nº 001/2026 para compra de medicamentos.',
          'Dispensa de Licitação nº 045/2026 para serviço de manutenção predial.',
          'Ato de nomeação sem relação com compras públicas.',
        ],
      });
      mockFetch.mockResolvedValue(makeQDResponse([gazette]));

      const results = await scraper.fetchLicitacoes({ size: 10 });

      // Two excerpts carry licitacao keywords; the third does not.
      expect(results).toHaveLength(2);
      const modalidades = results.map((r) => r.modalidade).sort();
      expect(modalidades).toEqual(['DISPENSA', 'PREGAO_ELETRONICO']);
    });

    it('infers modalidade from the excerpt text', async () => {
      const cases = [
        { text: 'Concorrência nº 003/2026 para obra de pavimentação.', expected: 'CONCORRENCIA' },
        { text: 'Tomada de preço nº 004/2026 para reforma de escola.', expected: 'TOMADA_DE_PRECOS' },
        { text: 'Inexigibilidade de licitação para contratação artística.', expected: 'INEXIGIBILIDADE' },
        { text: 'Chamamento público / credenciamento de prestadores.', expected: 'CREDENCIAMENTO' },
      ];

      for (const { text, expected } of cases) {
        mockFetch.mockResolvedValue(makeQDResponse([makeGazette({ excerpts: [text] })]));
        const results = await scraper.fetchLicitacoes({ size: 10 });
        expect(results[0].modalidade).toBe(expected);
      }
    });

    it('extracts BRL monetary values', async () => {
      const gazette = makeGazette({
        excerpts: ['Edital nº 077/2026. Valor global R$ 1.234.567,89 para aquisição de frota.'],
      });
      mockFetch.mockResolvedValue(makeQDResponse([gazette]));
      const results = await scraper.fetchLicitacoes({ size: 10 });
      expect(results[0].valorEstimado).toBe(1234567.89);
    });

    it('paginates across multiple pages', async () => {
      const full = Array.from({ length: 2 }, (_, i) =>
        makeGazette({ territory_id: `page1-${i}`, url: `https://qd/${i}.pdf` }),
      );
      const page2 = [makeGazette({ territory_id: 'page2-0', url: 'https://qd/p2.pdf' })];

      mockFetch
        .mockResolvedValueOnce(makeQDResponse(full, 4))
        .mockResolvedValueOnce(makeQDResponse(page2, 4));

      const results = await scraper.fetchLicitacoes({ size: 2 });

      expect(mockFetch).toHaveBeenCalledTimes(2);
      expect(results.length).toBe(3);
    });
  });
});
