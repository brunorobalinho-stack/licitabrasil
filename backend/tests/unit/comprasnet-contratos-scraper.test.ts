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

import { ComprasNetContratosScraper, ContratoItem } from '../../src/scrapers/federal/comprasnet-contratos-scraper.js';

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function makeContratoItem(overrides: Partial<ContratoItem> = {}): ContratoItem {
  return {
    codigoCategoria: '60',
    codigoModalidadeCompra: '05',
    codigoOrgao: '52121',
    codigoSubcategoria: null,
    codigoTipo: '98',
    codigoUnidadeGestora: '160399',
    codigoUnidadeGestoraOrigemContrato: '160399',
    codigoUnidadeRealizadoraCompra: '160399',
    contratoExcluido: false,
    dataHoraExclusao: null,
    dataHoraInclusao: '2025-09-29T12:07:25',
    dataVigenciaFinal: '2027-01-03T00:00:00',
    dataVigenciaInicial: '2026-02-01T00:00:00',
    idCompra: '16039905900052025',
    informacoesComplementares: null,
    niFornecedor: '09559385000104',
    nomeCategoria: 'Serviços',
    nomeModalidadeCompra: 'Pregão',
    nomeOrgao: 'COMANDO DO EXERCITO',
    nomeRazaoSocialFornecedor: 'MATRIX COMERCIALIZADORA DE ENERGIA ELÉTRICA S.A.',
    nomeSubcategoria: null,
    nomeTipo: 'Outros',
    nomeUnidadeGestora: 'HOSPITAL MILITAR DE AREA DE PORTO ALEGRE',
    nomeUnidadeGestoraOrigemContrato: 'HOSPITAL MILITAR DE AREA DE PORTO ALEGRE',
    nomeUnidadeRealizadoraCompra: 'HOSPITAL MILITAR DE AREA DE PORTO ALEGRE',
    numeroCompra: '90005/2025',
    numeroContrato: '00006/2025',
    numeroControlePncpContrato: null,
    numeroParcelas: 1,
    objeto: 'Contratação de empresa para fornecimento de energia elétrica na modalidade varejista',
    processo: '64286.004047/2025-32',
    receitaDespesa: 'D',
    totalDespesasAcessorias: null,
    unidadesRequisitantes: null,
    valorAcumulado: 4192299.0,
    valorGlobal: 4192299.0,
    valorParcela: 4192299.0,
    ...overrides,
  };
}

function makeApiResponse(resultado: ContratoItem[], paginasRestantes = 0) {
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

describe('ComprasNetContratosScraper', () => {
  let scraper: ComprasNetContratosScraper;

  beforeEach(() => {
    vi.clearAllMocks();
    globalThis.fetch = mockFetch;
    scraper = new ComprasNetContratosScraper(0);
  });

  it('has correct name and metadata', () => {
    expect(scraper.getName()).toBe('COMPRASNET_CONTRATOS');
    expect(scraper.getSourceUrl()).toBe('https://www.gov.br/compras');
    expect(scraper.getEsfera()).toBe('FEDERAL');
  });

  describe('buildUrl', () => {
    it('uses contratos endpoint with vigencia date params', () => {
      const url = scraper.buildUrl('2026-02-01', '2026-03-02', 1);
      expect(url).toContain('dadosabertos.compras.gov.br');
      expect(url).toContain('modulo-contratos/1_consultarContratos');
      expect(url).toContain('dataVigenciaInicialMin=2026-02-01');
      expect(url).toContain('dataVigenciaInicialMax=2026-03-02');
      expect(url).toContain('pagina=1');
    });
  });

  describe('mapToRawLicitacao', () => {
    it('maps Contrato item to RawLicitacao', () => {
      const r = scraper.mapToRawLicitacao(makeContratoItem());

      expect(r.fonteOrigem).toBe('COMPRASNET_CONTRATOS');
      expect(r.orgao).toBe('COMANDO DO EXERCITO');
      expect(r.codigoUASG).toBe('160399');
      expect(r.modalidade).toBe('Pregão');
      expect(r.objeto).toContain('fornecimento de energia elétrica');
      expect(r.valorEstimado).toBe(4192299);
      expect(r.valorMaximo).toBe(4192299);
      expect(r.valorMinimo).toBe(4192299);
      expect(r.status).toBe('homologada');
      expect(r.situacao).toBe('Contrato vigente');
      expect(r.dataPublicacao).toBe('2026-02-01');
      expect(r.dataEncerramento).toBe('2027-01-03');
      expect(r.numeroEdital).toBe('00006/2025');
      expect(r.numeroProcesso).toBe('64286.004047/2025-32');
    });

    it('includes fornecedor in segmento', () => {
      const r = scraper.mapToRawLicitacao(makeContratoItem());
      expect(r.segmento).toContain('MATRIX COMERCIALIZADORA');
    });

    it('maps categoria to tipo', () => {
      const servico = scraper.mapToRawLicitacao(makeContratoItem({ nomeCategoria: 'Serviços' }));
      expect(servico.tipo).toBe('serviço');

      const obra = scraper.mapToRawLicitacao(makeContratoItem({ nomeCategoria: 'Obras' }));
      expect(obra.tipo).toBe('obra');

      const compra = scraper.mapToRawLicitacao(makeContratoItem({ nomeCategoria: 'Compras' }));
      expect(compra.tipo).toBe('compra');
    });

    it('includes informacoesComplementares in objeto', () => {
      const r = scraper.mapToRawLicitacao(makeContratoItem({
        informacoesComplementares: 'Prazo de 60 meses',
      }));
      expect(r.objeto).toContain('fornecimento de energia');
      expect(r.objeto).toContain('Prazo de 60 meses');
    });

    it('falls back to nomeUnidadeGestora when no nomeOrgao', () => {
      const r = scraper.mapToRawLicitacao(makeContratoItem({
        nomeOrgao: undefined as any,
      }));
      expect(r.orgao).toBe('HOSPITAL MILITAR DE AREA DE PORTO ALEGRE');
    });

    it('builds PNCP url when controlePncp available', () => {
      const r = scraper.mapToRawLicitacao(makeContratoItem({
        numeroControlePncpContrato: '12345-1-000001/2026',
      }));
      expect(r.urlOrigem).toBe('https://pncp.gov.br/app/contratos/12345-1-000001/2026');
    });

    it('builds dadosabertos fallback url', () => {
      const r = scraper.mapToRawLicitacao(makeContratoItem({
        numeroControlePncpContrato: null,
      }));
      expect(r.urlOrigem).toContain('dadosabertos.compras.gov.br');
      expect(r.urlOrigem).toContain('16039905900052025');
    });
  });

  describe('fetchLicitacoes', () => {
    it('filters out excluded contratos', async () => {
      mockFetch.mockResolvedValueOnce(makeApiResponse([
        makeContratoItem(),
        makeContratoItem({ contratoExcluido: true, idCompra: 'excluido' }),
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
        .mockResolvedValueOnce(makeApiResponse([makeContratoItem()], 1))
        .mockResolvedValueOnce(makeApiResponse([makeContratoItem({ idCompra: 'page2' })], 0));

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
      mockFetch.mockResolvedValueOnce(makeApiResponse([makeContratoItem()]));

      const result = await scraper.run({});
      expect(result.source).toBe('COMPRASNET_CONTRATOS');
      expect(result.total).toBeGreaterThanOrEqual(1);
    });
  });
});
