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
    PNCP_API_BASE: 'https://pncp.gov.br/api/consulta',
    SCRAPING_RATE_LIMIT_MS: 0,
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

import { ComprasNetScraper } from '../../src/scrapers/federal/comprasnet-scraper.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function makeDadosAbertosItem(overrides: Record<string, unknown> = {}) {
  return {
    idCompra: '17000405000012026',
    numeroControlePNCP: '00394544000121-1-000001/2026',
    orgaoEntidadeCnpj: '00394544000121',
    orgaoEntidadeRazaoSocial: 'Ministério da Defesa',
    orgaoEntidadeEsferaId: 'F',
    unidadeOrgaoCodigoUnidade: '110404',
    unidadeOrgaoNomeUnidade: 'Secretaria-Geral',
    unidadeOrgaoUfSigla: 'DF',
    unidadeOrgaoMunicipioNome: 'Brasília',
    unidadeOrgaoCodigoIbge: 5300108,
    codigoModalidade: 5,
    modalidadeNome: 'Pregão',
    objetoCompra: 'Aquisição de material de expediente para as unidades do MD',
    valorTotalEstimado: 250000,
    valorTotalHomologado: null,
    dataPublicacaoPncp: '2026-03-01T09:00:00',
    dataAberturaPropostaPncp: '2026-03-15T10:00:00',
    dataEncerramentoPropostaPncp: '2026-03-20T18:00:00',
    situacaoCompraIdPncp: 1,
    situacaoCompraNomePncp: 'Divulgada no PNCP',
    amparoLegalNome: 'Lei 14.133/2021, Art. 28, I',
    amparoLegalDescricao: 'Pregão',
    modoDisputaNomePncp: 'Aberto',
    processo: '60585.000123/2026',
    numeroCompra: '001/2026',
    srp: false,
    informacaoComplementar: null,
    tipoInstrumentoConvocatorioNome: 'Edital',
    orcamentoSigilosoDescricao: 'Compra sem sigilo',
    contratacaoExcluida: false,
    ...overrides,
  };
}

function makeApiResponse(resultado: unknown[], paginasRestantes = 0) {
  return {
    ok: true,
    status: 200,
    json: () => Promise.resolve({
      resultado,
      totalRegistros: resultado.length,
      totalPaginas: 1,
      paginasRestantes,
    }),
    text: () => Promise.resolve(''),
  };
}

describe('ComprasNetScraper', () => {
  let scraper: ComprasNetScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new ComprasNetScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('COMPRASNET');
    expect(scraper.getSourceUrl()).toBe('https://www.gov.br/compras');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('buildUrl', () => {
    it('uses dadosabertos endpoint with correct params', () => {
      const url = scraper.buildUrl('2026-03-01', '2026-03-02', 1, 5);
      expect(url).toContain('dadosabertos.compras.gov.br');
      expect(url).toContain('modulo-contratacoes');
      expect(url).toContain('dataPublicacaoPncpInicial=2026-03-01');
      expect(url).toContain('dataPublicacaoPncpFinal=2026-03-02');
      expect(url).toContain('codigoModalidade=5');
      expect(url).toContain('pagina=1');
    });
  });

  describe('mapToRawLicitacao', () => {
    it('maps Dados Abertos item to RawLicitacao', () => {
      const item = makeDadosAbertosItem();
      const r = scraper.mapToRawLicitacao(item as any);

      expect(r.fonteOrigem).toBe('COMPRASNET');
      expect(r.orgao).toBe('Ministério da Defesa');
      expect(r.uf).toBe('DF');
      expect(r.municipio).toBe('Brasília');
      expect(r.codigoUASG).toBe('110404');
      expect(r.codigoPNCP).toContain('00394544000121');
      expect(r.objeto).toContain('material de expediente');
      expect(r.valorEstimado).toBe(250000);
      expect(r.modalidade).toBe('Pregão');
      expect(r.natureza).toContain('Lei 14.133');
      expect(r.regime).toBe('Aberto');
      expect(r.dataPublicacao).toBe('2026-03-01');
      expect(r.dataAbertura).toBe('2026-03-15');
      expect(r.dataEncerramento).toBe('2026-03-20');
      expect(r.urlOrigem).toContain('pncp.gov.br');
    });

    it('maps esfera correctly', () => {
      const federal = scraper.mapToRawLicitacao(makeDadosAbertosItem({ orgaoEntidadeEsferaId: 'F' }) as any);
      expect(federal.esfera).toBe('FEDERAL');

      const municipal = scraper.mapToRawLicitacao(makeDadosAbertosItem({ orgaoEntidadeEsferaId: 'M' }) as any);
      expect(municipal.esfera).toBe('MUNICIPAL');

      const estadual = scraper.mapToRawLicitacao(makeDadosAbertosItem({ orgaoEntidadeEsferaId: 'E' }) as any);
      expect(estadual.esfera).toBe('ESTADUAL');
    });

    it('includes informacaoComplementar in objeto', () => {
      const r = scraper.mapToRawLicitacao(makeDadosAbertosItem({
        informacaoComplementar: 'Detalhes adicionais sobre a contratação',
      }) as any);
      expect(r.objeto).toContain('material de expediente');
      expect(r.objeto).toContain('Detalhes adicionais');
    });

    it('marks SRP items in segmento', () => {
      const r = scraper.mapToRawLicitacao(makeDadosAbertosItem({ srp: true }) as any);
      expect(r.segmento).toBe('SRP');
    });
  });

  describe('fetchLicitacoes', () => {
    it('filters out excluded contratações', async () => {
      mockFetch
        .mockResolvedValueOnce(makeApiResponse([
          makeDadosAbertosItem(),
          makeDadosAbertosItem({ contratacaoExcluida: true, idCompra: 'excluida' }),
        ]))
        .mockResolvedValue(makeApiResponse([]));

      const results = await scraper.fetchLicitacoes({});

      expect(results).toHaveLength(1);
      expect(results[0].objeto).toContain('material de expediente');
    });

    it('handles empty response', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([]));
      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(0);
    });

    it('iterates through 8 modalidade codes', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([]));
      await scraper.fetchLicitacoes({});
      // 8 modalidades: 5, 6, 4, 7, 9, 1, 2, 3
      expect(mockFetch).toHaveBeenCalledTimes(8);
    });

    it('paginates when paginasRestantes > 0', async () => {
      mockFetch
        // Page 1 of modalidade 5: has more pages
        .mockResolvedValueOnce(makeApiResponse([makeDadosAbertosItem()], 1))
        // Page 2 of modalidade 5: no more
        .mockResolvedValueOnce(makeApiResponse([makeDadosAbertosItem({ idCompra: 'page2' })], 0))
        // Remaining modalidades: empty
        .mockResolvedValue(makeApiResponse([]));

      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(2);
    });

    it('maps situacao correctly', async () => {
      mockFetch
        .mockResolvedValueOnce(makeApiResponse([
          makeDadosAbertosItem({ situacaoCompraIdPncp: 2, situacaoCompraNomePncp: 'Aberta' }),
        ]))
        .mockResolvedValue(makeApiResponse([]));

      const results = await scraper.fetchLicitacoes({});
      expect(results[0].status).toBe('aberta');
    });
  });

  describe('run()', () => {
    it('returns ScrapingResult with correct source', async () => {
      mockFetch
        .mockResolvedValueOnce(makeApiResponse([makeDadosAbertosItem()]))
        .mockResolvedValue(makeApiResponse([]));

      const result = await scraper.run({});
      expect(result.source).toBe('COMPRASNET');
      expect(result.total).toBeGreaterThanOrEqual(1);
    });
  });
});
