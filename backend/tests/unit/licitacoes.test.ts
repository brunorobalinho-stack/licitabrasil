import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

/**
 * Unit tests for the /api/licitacoes routes.
 * Prisma and Redis cache are mocked.
 */

// ---------------------------------------------------------------------------
// Mocks — vi.hoisted() ensures these are available before vi.mock factories
// ---------------------------------------------------------------------------

const { mockPrisma, mockCache } = vi.hoisted(() => ({
  mockPrisma: {
    licitacao: {
      findMany: vi.fn(),
      findUnique: vi.fn(),
      count: vi.fn(),
      groupBy: vi.fn(),
      aggregate: vi.fn(),
    },
    $queryRawUnsafe: vi.fn(),
    $queryRaw: vi.fn(),
  },
  mockCache: {
    get: vi.fn().mockResolvedValue(null),
    set: vi.fn().mockResolvedValue(undefined),
    del: vi.fn().mockResolvedValue(undefined),
    invalidatePattern: vi.fn().mockResolvedValue(undefined),
  },
}));

vi.mock('../../src/lib/prisma.js', () => ({ prisma: mockPrisma }));
vi.mock('../../src/lib/redis.js', () => ({ cache: mockCache, redis: {} }));
vi.mock('../../src/lib/logger.js', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  },
}));

import { licitacoesRouter } from '../../src/api/routes/licitacoes.js';
import { errorHandler } from '../../src/api/middleware/error-handler.js';

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

let app: Express;

const sampleLicitacao = {
  id: 'lic1',
  numeroEdital: 'PE-001/2025',
  numeroProcesso: '123/2025',
  codigoPNCP: 'PNCP-001',
  modalidade: 'PREGAO_ELETRONICO',
  tipo: 'COMPRA',
  orgao: 'Ministério da Saúde',
  orgaoSigla: 'MS',
  esfera: 'FEDERAL',
  uf: 'DF',
  municipio: 'Brasília',
  objeto: 'Aquisição de equipamentos',
  objetoResumido: 'Aquisição de equipamentos',
  valorEstimado: 100000,
  dataPublicacao: '2025-01-15T00:00:00.000Z',
  dataAbertura: '2025-02-01T14:00:00.000Z',
  status: 'ABERTA',
  segmento: 'Saúde',
  fonteOrigem: 'PNCP',
  urlOrigem: 'https://pncp.gov.br/app/editais/001',
  criadoEm: '2025-01-15T10:00:00.000Z',
};

beforeEach(() => {
  app = express();
  app.use(express.json());
  app.use('/api/licitacoes', licitacoesRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
  mockCache.get.mockResolvedValue(null); // no cache hit by default
});

// ---------------------------------------------------------------------------
// GET /api/licitacoes
// ---------------------------------------------------------------------------

describe('GET /api/licitacoes', () => {
  it('returns paginated list', async () => {
    mockPrisma.licitacao.findMany.mockResolvedValue([sampleLicitacao]);
    mockPrisma.licitacao.count.mockResolvedValue(1);

    const res = await request(app).get('/api/licitacoes');

    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(1);
    expect(res.body.pagination.total).toBe(1);
    expect(res.body.pagination.page).toBe(1);
  });

  it('returns cached response when available', async () => {
    const cachedData = { data: [sampleLicitacao], pagination: { page: 1, pageSize: 20, total: 1, totalPages: 1 } };
    mockCache.get.mockResolvedValue(cachedData);

    const res = await request(app).get('/api/licitacoes');

    expect(res.status).toBe(200);
    expect(res.body).toEqual(cachedData);
    // Prisma should NOT have been called
    expect(mockPrisma.licitacao.findMany).not.toHaveBeenCalled();
  });

  it('applies esfera filter', async () => {
    mockPrisma.licitacao.findMany.mockResolvedValue([]);
    mockPrisma.licitacao.count.mockResolvedValue(0);

    await request(app).get('/api/licitacoes?esfera=FEDERAL');

    const whereArg = mockPrisma.licitacao.findMany.mock.calls[0][0].where;
    expect(whereArg.esfera).toBe('FEDERAL');
  });

  it('applies uf filter (uppercased)', async () => {
    mockPrisma.licitacao.findMany.mockResolvedValue([]);
    mockPrisma.licitacao.count.mockResolvedValue(0);

    await request(app).get('/api/licitacoes?uf=sp');

    const whereArg = mockPrisma.licitacao.findMany.mock.calls[0][0].where;
    expect(whereArg.uf).toBe('SP');
  });

  it('applies value range filter', async () => {
    mockPrisma.licitacao.findMany.mockResolvedValue([]);
    mockPrisma.licitacao.count.mockResolvedValue(0);

    await request(app).get('/api/licitacoes?valorMin=1000&valorMax=50000');

    const whereArg = mockPrisma.licitacao.findMany.mock.calls[0][0].where;
    expect(whereArg.valorEstimado.gte).toBe(1000);
    expect(whereArg.valorEstimado.lte).toBe(50000);
  });

  it('respects page and pageSize', async () => {
    mockPrisma.licitacao.findMany.mockResolvedValue([]);
    mockPrisma.licitacao.count.mockResolvedValue(50);

    await request(app).get('/api/licitacoes?page=3&pageSize=10');

    const call = mockPrisma.licitacao.findMany.mock.calls[0][0];
    expect(call.skip).toBe(20); // (3-1) * 10
    expect(call.take).toBe(10);
  });

  it('rejects invalid pageSize', async () => {
    const res = await request(app).get('/api/licitacoes?pageSize=200');
    expect(res.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// GET /api/licitacoes/search
// ---------------------------------------------------------------------------

describe('GET /api/licitacoes/search', () => {
  it('returns 400 when q is missing', async () => {
    const res = await request(app).get('/api/licitacoes/search');
    expect(res.status).toBe(400);
  });

  it('falls back to ILIKE when tsvector fails', async () => {
    mockPrisma.$queryRawUnsafe.mockRejectedValue(new Error('searchVector not available'));
    mockPrisma.licitacao.findMany.mockResolvedValue([sampleLicitacao]);
    mockPrisma.licitacao.count.mockResolvedValue(1);

    const res = await request(app).get('/api/licitacoes/search?q=equipamentos');

    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(1);
  });

  it('uses tsvector search when available', async () => {
    mockPrisma.$queryRawUnsafe
      .mockResolvedValueOnce([{ count: BigInt(1) }])
      .mockResolvedValueOnce([sampleLicitacao]);

    const res = await request(app).get('/api/licitacoes/search?q=equipamentos');

    expect(res.status).toBe(200);
    expect(mockPrisma.$queryRawUnsafe).toHaveBeenCalledTimes(2);
  });
});

// ---------------------------------------------------------------------------
// GET /api/licitacoes/stats
// ---------------------------------------------------------------------------

describe('GET /api/licitacoes/stats', () => {
  it('returns aggregate statistics', async () => {
    mockPrisma.licitacao.count
      .mockResolvedValueOnce(100) // totalCount
      .mockResolvedValueOnce(5);  // newToday
    mockPrisma.licitacao.groupBy
      .mockResolvedValueOnce([{ esfera: 'FEDERAL', _count: { id: 80 } }])
      .mockResolvedValueOnce([{ modalidade: 'PREGAO_ELETRONICO', _count: { id: 60 } }])
      .mockResolvedValueOnce([{ status: 'ABERTA', _count: { id: 30 } }]);
    mockPrisma.licitacao.aggregate.mockResolvedValue({
      _avg: { valorEstimado: 50000 },
    });

    const res = await request(app).get('/api/licitacoes/stats');

    expect(res.status).toBe(200);
    expect(res.body.total).toBe(100);
    expect(res.body.novasHoje).toBe(5);
    expect(res.body.porEsfera).toHaveLength(1);
    expect(res.body.porModalidade).toHaveLength(1);
  });
});

// ---------------------------------------------------------------------------
// GET /api/licitacoes/:id
// ---------------------------------------------------------------------------

describe('GET /api/licitacoes/:id', () => {
  it('returns single licitacao with relations', async () => {
    mockPrisma.licitacao.findUnique.mockResolvedValue({
      ...sampleLicitacao,
      itens: [],
      documentos: [],
      historico: [],
    });

    const res = await request(app).get('/api/licitacoes/lic1');

    expect(res.status).toBe(200);
    expect(res.body.id).toBe('lic1');
    expect(res.body.itens).toEqual([]);
  });

  it('returns 404 for non-existent id', async () => {
    mockPrisma.licitacao.findUnique.mockResolvedValue(null);

    const res = await request(app).get('/api/licitacoes/nonexistent');

    expect(res.status).toBe(404);
  });
});
