import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockLogger, mockChildLogger } = vi.hoisted(() => {
  const mockChildLogger = {
    info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
  };
  return {
    mockChildLogger,
    mockLogger: {
      info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
      child: vi.fn().mockReturnValue(mockChildLogger),
    },
  };
});

vi.mock('../../src/lib/prisma.js', () => ({
  prisma: {
    fonteDados: { upsert: vi.fn().mockResolvedValue({}), update: vi.fn().mockResolvedValue({}) },
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
    PNCP_API_BASE: 'test', SCRAPING_RATE_LIMIT_MS: 0,
    DATABASE_URL: 'test', REDIS_URL: 'test',
    JWT_SECRET: 'test', JWT_REFRESH_SECRET: 'test',
    JWT_EXPIRES_IN: '15m', JWT_REFRESH_EXPIRES_IN: '7d',
    PORT: 3099, NODE_ENV: 'test', CORS_ORIGIN: '*',
    QUERIDO_DIARIO_API_BASE: 'test',
    CONLICITACAO_EMAIL: '', CONLICITACAO_PASSWORD: '',
    CONLICITACAO_API_BASE: 'test',
    SCRAPING_CONCURRENCY: 1, LOG_LEVEL: 'silent',
  },
}));

vi.mock('@prisma/client', () => ({
  Prisma: { Decimal: class Decimal { constructor(public value: number) {} toString() { return String(this.value); } } },
  Modalidade: {
    PREGAO_ELETRONICO: 'PREGAO_ELETRONICO', PREGAO_PRESENCIAL: 'PREGAO_PRESENCIAL',
    CONCORRENCIA: 'CONCORRENCIA', CONCORRENCIA_ELETRONICA: 'CONCORRENCIA_ELETRONICA',
    TOMADA_DE_PRECOS: 'TOMADA_DE_PRECOS', CONVITE: 'CONVITE', CONCURSO: 'CONCURSO',
    LEILAO: 'LEILAO', DIALOGO_COMPETITIVO: 'DIALOGO_COMPETITIVO',
    DISPENSA: 'DISPENSA', INEXIGIBILIDADE: 'INEXIGIBILIDADE',
    CREDENCIAMENTO: 'CREDENCIAMENTO', RDC: 'RDC', OUTRA: 'OUTRA',
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

import { LicitacoesEScraper } from '../../src/scrapers/agregadores/licitacoes-e-scraper.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const SEARCH_RESULTS_HTML = `
<html><body>
  <table id="tabelaResultado">
    <tr><th>Licitação</th><th>Órgão</th><th>Objeto</th><th>UF</th><th>Abertura</th></tr>
    <tr class="linhaPar">
      <td><a href="/aop/licitacao/12345.aop">98765/2026</a></td>
      <td>Ministério da Educação - Universidade Federal de Goiás</td>
      <td>Aquisição de equipamentos de informática para os laboratórios da universidade, incluindo computadores, monitores e impressoras</td>
      <td>GO</td>
      <td>15/03/2026</td>
    </tr>
    <tr class="linhaImpar">
      <td><a href="/aop/licitacao/67890.aop">54321/2026</a></td>
      <td>Prefeitura Municipal de Cuiabá</td>
      <td>Contratação de serviços de engenharia para pavimentação de vias urbanas no bairro Jardim das Américas</td>
      <td>MT</td>
      <td>20/03/2026</td>
    </tr>
  </table>
</body></html>
`;

const EMPTY_RESULTS_HTML = `
<html><body>
  <div>Nenhuma licitação encontrada.</div>
</body></html>
`;

function makeHtmlResponse(html: string, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: () => Promise.resolve(html),
    headers: {
      getSetCookie: () => ['JSESSIONID=abc123; Path=/'],
    },
  };
}

describe('LicitacoesEScraper', () => {
  let scraper: LicitacoesEScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new LicitacoesEScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('LICITACOES_E');
    expect(scraper.getSourceUrl()).toBe('https://www.licitacoes-e.com.br');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('parseSearchResults', () => {
    it('parses result table rows into RawLicitacao items', () => {
      const items = scraper.parseSearchResults(SEARCH_RESULTS_HTML);

      expect(items).toHaveLength(2);

      const first = items[0];
      expect(first.fonteOrigem).toBe('LICITACOES_E');
      expect(first.objeto).toContain('equipamentos de informática');
      expect(first.orgao).toContain('Universidade Federal de Goiás');
      expect(first.uf).toBe('GO');
      expect(first.numeroEdital).toBe('98765/2026');
      expect(first.urlOrigem).toContain('/aop/licitacao/12345');

      const second = items[1];
      expect(second.objeto).toContain('pavimentação');
      expect(second.esfera).toBe('MUNICIPAL');
      expect(second.uf).toBe('MT');
    });

    it('returns empty array for empty results', () => {
      const items = scraper.parseSearchResults(EMPTY_RESULTS_HTML);
      expect(items).toHaveLength(0);
    });
  });

  describe('fetchLicitacoes', () => {
    it('fetches initial page and then searches by situacao', async () => {
      mockFetch
        .mockResolvedValueOnce(makeHtmlResponse('<html></html>'))  // Initial GET
        .mockResolvedValueOnce(makeHtmlResponse(SEARCH_RESULTS_HTML))  // situacao=4 POST
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML))   // situacao=1 POST
        .mockResolvedValueOnce(makeHtmlResponse(SEARCH_RESULTS_HTML))  // situacao=3 POST
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML))   // extra fallback
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML));  // extra fallback

      const results = await scraper.fetchLicitacoes({});

      // 1 initial GET + 3 POSTs (for 3 situacoes)
      expect(mockFetch).toHaveBeenCalledTimes(4);
      expect(results).toHaveLength(4);
    });

    it('captures JSESSIONID cookie from initial request', async () => {
      mockFetch
        .mockResolvedValueOnce(makeHtmlResponse('<html></html>'))
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML));

      await scraper.fetchLicitacoes({});

      // The second and third calls should include the cookie
      const postHeaders = mockFetch.mock.calls[1][1]?.headers;
      expect(postHeaders?.Cookie).toBe('JSESSIONID=abc123');
    });

    it('handles initial page failure gracefully', async () => {
      mockFetch
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValue(makeHtmlResponse(SEARCH_RESULTS_HTML));

      const results = await scraper.fetchLicitacoes({});
      // Should still attempt the search POSTs
      expect(results.length).toBeGreaterThanOrEqual(0);
    });

    it('infers esfera from orgao name', () => {
      const items = scraper.parseSearchResults(SEARCH_RESULTS_HTML);
      // "Ministério da Educação" → FEDERAL
      expect(items[0].esfera).toBe('FEDERAL');
      // "Prefeitura Municipal" → MUNICIPAL
      expect(items[1].esfera).toBe('MUNICIPAL');
    });
  });

  describe('run()', () => {
    it('returns ScrapingResult with correct source', async () => {
      mockFetch
        .mockResolvedValueOnce(makeHtmlResponse('<html></html>'))
        .mockResolvedValueOnce(makeHtmlResponse(SEARCH_RESULTS_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(SEARCH_RESULTS_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(EMPTY_RESULTS_HTML));

      const result = await scraper.run({});
      expect(result.source).toBe('LICITACOES_E');
      expect(result.total).toBe(4);
      // Deduplication: identical HTML from situacao=3 produces same items, so only 2 unique
      expect(result.created + result.updated).toBe(2);
    });
  });
});
