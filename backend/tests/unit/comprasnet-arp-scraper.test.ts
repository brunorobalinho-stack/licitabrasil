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

import { ComprasNetARPScraper, ARPItem } from '../../src/scrapers/federal/comprasnet-arp-scraper.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function makeARPItem(overrides: Partial<ARPItem> = {}): ARPItem {
  return {
    anoCompra: '2026',
    ataExcluido: false,
    codigoModalidadeCompra: '05',
    codigoOrgao: null,
    codigoUnidadeGerenciadora: '783810',
    dataAssinatura: '2026-02-05T00:00:00',
    dataHoraAtualizacao: '2026-02-24T15:50:14',
    dataHoraExclusao: null,
    dataHoraInclusao: '2026-02-24T15:46:53',
    dataVigenciaFinal: '2027-02-06',
    dataVigenciaInicial: '2026-02-06',
    idCompra: '78381005900052025',
    linkAtaPNCP: 'https://pncp.gov.br/app/atas/00394502002864/2025/3509/36',
    linkCompraPNCP: 'https://pncp.gov.br/app/editais/00394502002864/2025/003509',
    nomeModalidadeCompra: 'Pregão',
    nomeOrgao: null,
    nomeUnidadeGerenciadora: 'CENTRO DE INTENDENCIA DA MARINHA EM NATAL',
    numeroAtaRegistroPreco: '00022/2026',
    numeroCompra: '90005',
    numeroControlePncpAta: '00394502002864-1-003509/2025-000036',
    numeroControlePncpCompra: '00394502002864-1-003509/2025',
    objeto: 'Aquisição de material eletroeletrônico e de comunicação para a Marinha',
    quantidadeItens: 1,
    statusAta: 'Ata de Registro de Preços',
    valorTotal: 8260.0,
    ...overrides,
  };
}

function makeApiResponse(resultado: ARPItem[], paginasRestantes = 0) {
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

describe('ComprasNetARPScraper', () => {
  let scraper: ComprasNetARPScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new ComprasNetARPScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('COMPRASNET_ARP');
    expect(scraper.getSourceUrl()).toBe('https://www.gov.br/compras');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('buildUrl', () => {
    it('uses ARP endpoint with vigencia date params', () => {
      const url = scraper.buildUrl('2026-02-01', '2026-03-02', 1);
      expect(url).toContain('dadosabertos.compras.gov.br');
      expect(url).toContain('modulo-arp/1_consultarARP');
      expect(url).toContain('dataVigenciaInicialMin=2026-02-01');
      expect(url).toContain('dataVigenciaInicialMax=2026-03-02');
      expect(url).toContain('pagina=1');
    });
  });

  describe('mapToRawLicitacao', () => {
    it('maps ARP item to RawLicitacao', () => {
      const r = scraper.mapToRawLicitacao(makeARPItem());

      expect(r.fonteOrigem).toBe('COMPRASNET_ARP');
      expect(r.orgao).toBe('CENTRO DE INTENDENCIA DA MARINHA EM NATAL');
      expect(r.codigoUASG).toBe('783810');
      expect(r.codigoPNCP).toBe('00394502002864-1-003509/2025-000036');
      expect(r.modalidade).toBe('Pregão');
      expect(r.objeto).toContain('material eletroeletrônico');
      expect(r.valorEstimado).toBe(8260);
      expect(r.segmento).toBe('SRP');
      expect(r.dataPublicacao).toBe('2026-02-06');
      expect(r.dataEncerramento).toBe('2027-02-06');
      expect(r.urlEdital).toContain('pncp.gov.br/app/atas');
    });

    it('uses numero ata as edital number', () => {
      const r = scraper.mapToRawLicitacao(makeARPItem());
      expect(r.numeroEdital).toBe('00022/2026');
    });

    it('includes linkCompraPNCP in urlAnexos', () => {
      const r = scraper.mapToRawLicitacao(makeARPItem());
      expect(r.urlAnexos).toContain('https://pncp.gov.br/app/editais/00394502002864/2025/003509');
    });

    it('falls back to nomeOrgao when no unidade', () => {
      const r = scraper.mapToRawLicitacao(makeARPItem({
        nomeUnidadeGerenciadora: undefined as any,
        nomeOrgao: 'MINISTERIO DA DEFESA',
      }));
      expect(r.orgao).toBe('MINISTERIO DA DEFESA');
    });

    it('uses dataAssinatura for dataAbertura', () => {
      const r = scraper.mapToRawLicitacao(makeARPItem());
      expect(r.dataAbertura).toBe('2026-02-05');
    });
  });

  describe('fetchLicitacoes', () => {
    it('filters out excluded atas', async () => {
      mockFetch.mockResolvedValueOnce(makeApiResponse([
        makeARPItem(),
        makeARPItem({ ataExcluido: true, idCompra: 'excluida' }),
      ]));

      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(1);
    });

    it('handles empty response', async () => {
      mockFetch.mockResolvedValue(makeApiResponse([]));
      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(0);
    });

    it('paginates when paginasRestantes > 0', async () => {
      mockFetch
        .mockResolvedValueOnce(makeApiResponse([makeARPItem()], 1))
        .mockResolvedValueOnce(makeApiResponse([makeARPItem({ idCompra: 'page2' })], 0));

      const results = await scraper.fetchLicitacoes({});
      expect(results).toHaveLength(2);
      expect(mockFetch).toHaveBeenCalledTimes(2);
    });

    it('makes single request (no modalidade loop)', async () => {
      mockFetch.mockResolvedValueOnce(makeApiResponse([]));
      await scraper.fetchLicitacoes({});
      expect(mockFetch).toHaveBeenCalledTimes(1);
    });
  });

  describe('run()', () => {
    it('returns ScrapingResult with correct source', async () => {
      mockFetch.mockResolvedValueOnce(makeApiResponse([makeARPItem()]));

      const result = await scraper.run({});
      expect(result.source).toBe('COMPRASNET_ARP');
      expect(result.total).toBeGreaterThanOrEqual(1);
    });
  });
});
