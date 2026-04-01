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

import { DOUScraper } from '../../src/scrapers/federal/dou-scraper.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

const SAMPLE_DOU_HTML = `
<html><body>
  <div class="resultado-busca-dou">
    <p class="title"><a href="/web/dou/-/aviso-de-licitacao-123456">Aviso de Licitação - Pregão Eletrônico nº 045/2026</a></p>
    <span class="secao-dou">SEÇÃO 3 | MINISTÉRIO DA EDUCAÇÃO | Universidade Federal do ABC</span>
    <span class="date-dou">02/03/2026</span>
    <span class="edicao-dou">Edição 42, p. 153</span>
    <p class="abstract-dou">Contratação de serviços de vigilância patrimonial para o campus de Santo André. Valor estimado: R$ 1.500.000,00. Abertura: 20/03/2026.</p>
  </div>
  <div class="resultado-busca-dou">
    <p class="title"><a href="/web/dou/-/aviso-de-licitacao-789012">Aviso de Licitação - Concorrência nº 003/2026</a></p>
    <span class="secao-dou">SEÇÃO 3 | MINISTÉRIO DA SAÚDE</span>
    <span class="date-dou">02/03/2026</span>
    <p class="abstract-dou">Obra de reforma do Hospital Federal de Bonsucesso. Valor: R$ 8.200.000,00</p>
  </div>
</body></html>
`;

function makeHtmlResponse(html: string) {
  return {
    ok: true,
    status: 200,
    text: () => Promise.resolve(html),
  };
}

describe('DOUScraper', () => {
  let scraper: DOUScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new DOUScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('DOU');
    expect(scraper.getSourceUrl()).toBe('https://www.in.gov.br/web/dou');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('parseSearchResults', () => {
    it('parses DOU HTML into RawLicitacao items', () => {
      const items = scraper.parseSearchResults(SAMPLE_DOU_HTML);

      expect(items).toHaveLength(2);

      const first = items[0];
      expect(first.fonteOrigem).toBe('DOU');
      expect(first.esfera).toBe('FEDERAL');
      expect(first.orgao).toContain('MINISTÉRIO DA EDUCAÇÃO');
      expect(first.objeto).toContain('vigilância patrimonial');
      expect(first.valorEstimado).toBe(1500000);
      expect(first.dataPublicacao).toBe('2026-03-02');
      expect(first.dataAbertura).toBe('2026-03-20');
      expect(first.urlOrigem).toContain('/web/dou/-/aviso-de-licitacao-123456');

      const second = items[1];
      expect(second.orgao).toContain('MINISTÉRIO DA SAÚDE');
      expect(second.objeto).toContain('reforma do Hospital');
      expect(second.valorEstimado).toBe(8200000);
    });

    it('returns empty array for empty HTML', () => {
      const items = scraper.parseSearchResults('<html><body></body></html>');
      expect(items).toHaveLength(0);
    });
  });

  describe('fetchLicitacoes', () => {
    it('fetches and parses DOU search results', async () => {
      mockFetch.mockResolvedValue(makeHtmlResponse(SAMPLE_DOU_HTML));

      const results = await scraper.fetchLicitacoes({ pageSize: 20 });

      expect(results).toHaveLength(2);
      expect(mockFetch).toHaveBeenCalledTimes(1);

      const url = mockFetch.mock.calls[0][0] as string;
      expect(url).toContain('in.gov.br/consulta');
      expect(url).toContain('s=do3');
    });

    it('handles fetch error gracefully', async () => {
      mockFetch.mockRejectedValue(new Error('Network error'));

      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(0);
    });

    it('uses custom query parameter', async () => {
      mockFetch.mockResolvedValue(makeHtmlResponse('<html><body></body></html>'));

      await scraper.fetchLicitacoes({ query: 'pregão eletrônico' });

      const url = mockFetch.mock.calls[0][0] as string;
      // URLSearchParams encodes spaces as '+', not '%20'
      expect(url).toContain('%22preg%C3%A3o+eletr%C3%B4nico%22');
    });
  });

  describe('run()', () => {
    it('returns ScrapingResult with correct source', async () => {
      mockFetch.mockResolvedValue(makeHtmlResponse(SAMPLE_DOU_HTML));
      const result = await scraper.run({});
      expect(result.source).toBe('DOU');
      expect(result.total).toBe(2);
      expect(result.created).toBe(2);
    });
  });
});
