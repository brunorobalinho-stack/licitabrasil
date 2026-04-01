import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const { mockPrisma, mockCache } = vi.hoisted(() => ({
  mockPrisma: {
    fonteDados: {
      findMany: vi.fn(),
    },
    licitacao: {
      groupBy: vi.fn(),
    },
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

import { fontesRouter } from '../../src/api/routes/fontes.js';
import { errorHandler } from '../../src/api/middleware/error-handler.js';

let app: Express;

const now = new Date();

const sampleFonte = {
  id: 'f1',
  nome: 'PNCP',
  url: 'https://pncp.gov.br',
  tipo: 'API',
  esfera: 'FEDERAL',
  ativo: true,
  intervaloMinutos: 60,
  ultimaColeta: now,
  ultimoSucesso: new Date(now.getTime() - 30 * 60 * 1000), // 30 min ago
  ultimaFalha: null,
  totalColetados: 1000,
  totalErros: 5,
};

beforeEach(() => {
  app = express();
  app.use(express.json());
  app.use('/api/fontes', fontesRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
  mockCache.get.mockResolvedValue(null);
});

// ---------------------------------------------------------------------------
// GET /api/fontes/status
// ---------------------------------------------------------------------------

describe('GET /api/fontes/status', () => {
  it('returns fonte list with healthy flag', async () => {
    mockPrisma.fonteDados.findMany.mockResolvedValue([sampleFonte]);

    const res = await request(app).get('/api/fontes/status');

    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].nome).toBe('PNCP');
    expect(res.body[0].healthy).toBe(true);
  });

  it('marks fonte as unhealthy when last success is too old', async () => {
    const stale = {
      ...sampleFonte,
      ultimoSucesso: new Date(now.getTime() - 3 * 60 * 60 * 1000), // 3h ago (> 2x 60min)
    };
    mockPrisma.fonteDados.findMany.mockResolvedValue([stale]);

    const res = await request(app).get('/api/fontes/status');

    expect(res.body[0].healthy).toBe(false);
  });

  it('marks fonte as unhealthy when failure is after success', async () => {
    const failed = {
      ...sampleFonte,
      ultimaFalha: new Date(now.getTime() - 10 * 60 * 1000), // 10 min ago
      ultimoSucesso: new Date(now.getTime() - 20 * 60 * 1000), // 20 min ago
    };
    mockPrisma.fonteDados.findMany.mockResolvedValue([failed]);

    const res = await request(app).get('/api/fontes/status');

    expect(res.body[0].healthy).toBe(false);
  });

  it('marks fonte as unhealthy when never succeeded', async () => {
    const never = { ...sampleFonte, ultimoSucesso: null };
    mockPrisma.fonteDados.findMany.mockResolvedValue([never]);

    const res = await request(app).get('/api/fontes/status');

    expect(res.body[0].healthy).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// GET /api/fontes/cobertura
// ---------------------------------------------------------------------------

describe('GET /api/fontes/cobertura', () => {
  it('returns coverage by esfera and UF', async () => {
    mockPrisma.licitacao.groupBy
      .mockResolvedValueOnce([ // by esfera
        { esfera: 'FEDERAL', _count: { id: 500 } },
        { esfera: 'ESTADUAL', _count: { id: 200 } },
      ])
      .mockResolvedValueOnce([ // by uf
        { uf: 'SP', _count: { id: 300 } },
        { uf: 'RJ', _count: { id: 150 } },
      ]);

    const res = await request(app).get('/api/fontes/cobertura');

    expect(res.status).toBe(200);
    expect(res.body.federal).toBe(500);
    expect(res.body.estadual).toBe(200);
    expect(res.body.municipal).toBe(0);
    expect(res.body.porEstado.SP).toBe(300);
  });

  it('returns cached cobertura', async () => {
    const cached = { federal: 100, estadual: 50, municipal: 10, porEstado: { SP: 60 } };
    mockCache.get.mockResolvedValue(cached);

    const res = await request(app).get('/api/fontes/cobertura');

    expect(res.status).toBe(200);
    expect(res.body).toEqual(cached);
    expect(mockPrisma.licitacao.groupBy).not.toHaveBeenCalled();
  });

  it('caches the result for 30 minutes', async () => {
    mockPrisma.licitacao.groupBy.mockResolvedValue([]);

    await request(app).get('/api/fontes/cobertura');

    expect(mockCache.set).toHaveBeenCalledWith('fontes:cobertura', expect.any(Object), 1800);
  });
});
