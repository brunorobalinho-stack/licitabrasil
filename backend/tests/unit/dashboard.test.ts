import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const { mockPrisma, mockCache } = vi.hoisted(() => ({
  mockPrisma: {
    licitacao: {
      count: vi.fn(),
      aggregate: vi.fn(),
      groupBy: vi.fn(),
    },
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
    info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  },
}));

import { dashboardRouter } from '../../src/api/routes/dashboard.js';
import { errorHandler } from '../../src/api/middleware/error-handler.js';

let app: Express;

beforeEach(() => {
  app = express();
  app.use(express.json());
  app.use('/api/dashboard', dashboardRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
  mockCache.get.mockResolvedValue(null);
});

// ---------------------------------------------------------------------------
// GET /api/dashboard/resumo
// ---------------------------------------------------------------------------

describe('GET /api/dashboard/resumo', () => {
  it('returns summary stats', async () => {
    mockPrisma.licitacao.count
      .mockResolvedValueOnce(10) // novasHoje
      .mockResolvedValueOnce(50) // abertasEstaSemana
      .mockResolvedValueOnce(5); // encerradasEstaSemana
    mockPrisma.licitacao.aggregate.mockResolvedValue({
      _sum: { valorEstimado: 1000000 },
    });

    const res = await request(app).get('/api/dashboard/resumo');

    expect(res.status).toBe(200);
    expect(res.body.novasHoje).toBe(10);
    expect(res.body.abertasEstaSemana).toBe(50);
    expect(res.body.volumeTotalAbertas).toBe(1000000);
  });

  it('returns cached response when available', async () => {
    const cached = { novasHoje: 5, abertasEstaSemana: 20, encerradasEstaSemana: 3, volumeTotalAbertas: 500000 };
    mockCache.get.mockResolvedValue(cached);

    const res = await request(app).get('/api/dashboard/resumo');

    expect(res.status).toBe(200);
    expect(res.body).toEqual(cached);
    expect(mockPrisma.licitacao.count).not.toHaveBeenCalled();
  });

  it('caches the result', async () => {
    mockPrisma.licitacao.count.mockResolvedValue(0);
    mockPrisma.licitacao.aggregate.mockResolvedValue({ _sum: { valorEstimado: null } });

    await request(app).get('/api/dashboard/resumo');

    expect(mockCache.set).toHaveBeenCalledWith('dashboard:resumo', expect.any(Object), 300);
  });
});

// ---------------------------------------------------------------------------
// GET /api/dashboard/por-estado
// ---------------------------------------------------------------------------

describe('GET /api/dashboard/por-estado', () => {
  it('returns counts grouped by UF', async () => {
    mockPrisma.licitacao.groupBy.mockResolvedValue([
      { uf: 'SP', _count: { id: 100 } },
      { uf: 'RJ', _count: { id: 50 } },
    ]);

    const res = await request(app).get('/api/dashboard/por-estado');

    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(2);
    expect(res.body[0].uf).toBe('SP');
    expect(res.body[0].count).toBe(100);
  });
});

// ---------------------------------------------------------------------------
// GET /api/dashboard/por-modalidade
// ---------------------------------------------------------------------------

describe('GET /api/dashboard/por-modalidade', () => {
  it('returns counts grouped by modalidade', async () => {
    mockPrisma.licitacao.groupBy.mockResolvedValue([
      { modalidade: 'PREGAO_ELETRONICO', _count: { id: 80 } },
    ]);

    const res = await request(app).get('/api/dashboard/por-modalidade');

    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].modalidade).toBe('PREGAO_ELETRONICO');
  });
});

// ---------------------------------------------------------------------------
// GET /api/dashboard/tendencias
// ---------------------------------------------------------------------------

describe('GET /api/dashboard/tendencias', () => {
  it('returns daily publication counts', async () => {
    mockPrisma.$queryRaw.mockResolvedValue([
      { date: '2025-01-15', count: BigInt(10) },
      { date: '2025-01-16', count: BigInt(15) },
    ]);

    const res = await request(app).get('/api/dashboard/tendencias');

    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(2);
    expect(res.body[0].count).toBe(10);
    expect(res.body[1].count).toBe(15);
  });
});
