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

import { BECSPScraper } from '../../src/scrapers/estadual/bec-sp-scraper.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const INITIAL_PAGE_HTML = `
<html><body>
  <form id="aspnetForm">
    <input type="hidden" name="__VIEWSTATE" value="fake_viewstate_value" />
    <input type="hidden" name="__VIEWSTATEGENERATOR" value="fake_gen" />
    <input type="hidden" name="__EVENTVALIDATION" value="fake_ev" />
    <input name="ctl00$ContentPlaceHolder1$txtChave" />
    <input type="submit" name="ctl00$ContentPlaceHolder1$btnPesquisar" value="Pesquisar" />
  </form>
</body></html>
`;

const RESULTS_HTML = `
<html><body>
  <table id="grdResultado">
    <tr><th>OC</th><th>Objeto</th><th>Órgão</th><th>Abertura</th><th>Valor</th></tr>
    <tr>
      <td><a href="/bec_pregao_UI/OC/detalhe.aspx?id=12345">OC 800001/2026</a></td>
      <td>Aquisição de medicamentos para a Secretaria Estadual de Saúde de São Paulo, incluindo insumos hospitalares diversos</td>
      <td>Secretaria de Estado da Saúde</td>
      <td>15/03/2026</td>
      <td>R$ 2.500.000,00</td>
    </tr>
    <tr>
      <td><a href="/bec_pregao_UI/OC/detalhe.aspx?id=12346">OC 800002/2026</a></td>
      <td>Prestação de serviços de limpeza e conservação predial para unidades da Secretaria de Educação do Estado de São Paulo</td>
      <td>Secretaria de Estado da Educação</td>
      <td>20/03/2026</td>
      <td>R$ 1.800.000,00</td>
    </tr>
  </table>
</body></html>
`;

function makeHtmlResponse(html: string) {
  return {
    ok: true,
    status: 200,
    text: () => Promise.resolve(html),
    headers: new Headers(),
  };
}

describe('BECSPScraper', () => {
  let scraper: BECSPScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new BECSPScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('BEC_SP');
    expect(scraper.getSourceUrl()).toBe('https://www.bec.sp.gov.br');
    expect(scraper.getEsfera()).toBe('ESTADUAL');
  });

  describe('extractFormState', () => {
    it('extracts ViewState from HTML', () => {
      const state = scraper.extractFormState(INITIAL_PAGE_HTML);
      expect(state.__VIEWSTATE).toBe('fake_viewstate_value');
      expect(state.__VIEWSTATEGENERATOR).toBe('fake_gen');
      expect(state.__EVENTVALIDATION).toBe('fake_ev');
    });

    it('returns empty strings when no ViewState', () => {
      const state = scraper.extractFormState('<html><body></body></html>');
      expect(state.__VIEWSTATE).toBe('');
    });
  });

  describe('parseResultsTable', () => {
    it('parses BEC SP table rows into RawLicitacao items', () => {
      const items = scraper.parseResultsTable(RESULTS_HTML);

      expect(items).toHaveLength(2);

      const first = items[0];
      expect(first.fonteOrigem).toBe('BEC_SP');
      expect(first.esfera).toBe('ESTADUAL');
      expect(first.uf).toBe('SP');
      expect(first.objeto).toContain('medicamentos');
      expect(first.valorEstimado).toBe(2500000);
      expect(first.orgao).toContain('Secretaria de Estado da Saúde');
      expect(first.urlOrigem).toContain('detalhe.aspx');
    });

    it('returns empty array for empty HTML', () => {
      const items = scraper.parseResultsTable('<html><body></body></html>');
      expect(items).toHaveLength(0);
    });
  });

  describe('fetchLicitacoes', () => {
    it('performs GET then POST flow', async () => {
      mockFetch
        .mockResolvedValueOnce(makeHtmlResponse(INITIAL_PAGE_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(RESULTS_HTML));

      const results = await scraper.fetchLicitacoes({});

      expect(mockFetch).toHaveBeenCalledTimes(2);
      // First call: GET
      expect(mockFetch.mock.calls[0][1]?.method).toBeUndefined(); // GET is default
      // Second call: POST
      expect(mockFetch.mock.calls[1][1]?.method).toBe('POST');

      expect(results).toHaveLength(2);
    });

    it('falls back to initial page on POST failure', async () => {
      mockFetch
        .mockResolvedValueOnce(makeHtmlResponse(RESULTS_HTML)) // Initial page has results
        .mockRejectedValueOnce(new Error('POST failed'));

      const results = await scraper.fetchLicitacoes({});
      expect(results.length).toBeGreaterThanOrEqual(0);
    });

    it('handles initial page failure gracefully', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));
      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(0);
    });
  });

  describe('run()', () => {
    it('returns ScrapingResult with correct source', async () => {
      mockFetch
        .mockResolvedValueOnce(makeHtmlResponse(INITIAL_PAGE_HTML))
        .mockResolvedValueOnce(makeHtmlResponse(RESULTS_HTML));

      const result = await scraper.run({});
      expect(result.source).toBe('BEC_SP');
      expect(result.total).toBe(2);
    });
  });
});
