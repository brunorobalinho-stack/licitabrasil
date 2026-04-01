import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    buscaSalva: {
      create: vi.fn(),
      findMany: vi.fn(),
      findUnique: vi.fn(),
      delete: vi.fn(),
    },
  },
}));

vi.mock('../../src/lib/prisma.js', () => ({ prisma: mockPrisma }));
vi.mock('../../src/lib/logger.js', () => ({
  logger: {
    info: vi.fn(), warn: vi.fn(), error: vi.fn(), debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  },
}));

import { buscasSalvasRouter } from '../../src/api/routes/buscas-salvas.js';
import { errorHandler } from '../../src/api/middleware/error-handler.js';

let app: Express;

const fakeAuth = (req: express.Request, _res: express.Response, next: express.NextFunction) => {
  req.user = { userId: 'u1', email: 'test@test.com' };
  next();
};

beforeEach(() => {
  app = express();
  app.use(express.json());
  app.use(fakeAuth);
  app.use('/api/buscas-salvas', buscasSalvasRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// POST /api/buscas-salvas
// ---------------------------------------------------------------------------

describe('POST /api/buscas-salvas', () => {
  it('creates a saved search', async () => {
    mockPrisma.buscaSalva.create.mockResolvedValue({
      id: 'b1', usuarioId: 'u1', nome: 'Saúde Federal', filtros: { esfera: 'FEDERAL' },
    });

    const res = await request(app).post('/api/buscas-salvas').send({
      nome: 'Saúde Federal',
      filtros: { esfera: 'FEDERAL' },
    });

    expect(res.status).toBe(201);
    expect(res.body.id).toBe('b1');
  });

  it('returns 400 when nome is empty', async () => {
    const res = await request(app).post('/api/buscas-salvas').send({
      nome: '',
      filtros: { esfera: 'FEDERAL' },
    });
    expect(res.status).toBe(400);
  });

  it('returns 400 when filtros is empty object', async () => {
    const res = await request(app).post('/api/buscas-salvas').send({
      nome: 'Test',
      filtros: {},
    });
    expect(res.status).toBe(400);
  });

  it('returns 400 when filtros is missing', async () => {
    const res = await request(app).post('/api/buscas-salvas').send({ nome: 'Test' });
    expect(res.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// GET /api/buscas-salvas
// ---------------------------------------------------------------------------

describe('GET /api/buscas-salvas', () => {
  it('returns list of saved searches', async () => {
    mockPrisma.buscaSalva.findMany.mockResolvedValue([
      { id: 'b1', nome: 'Saúde', filtros: { esfera: 'FEDERAL' } },
    ]);

    const res = await request(app).get('/api/buscas-salvas');

    expect(res.status).toBe(200);
    expect(res.body).toHaveLength(1);
    expect(res.body[0].nome).toBe('Saúde');
  });

  it('filters by current user', async () => {
    mockPrisma.buscaSalva.findMany.mockResolvedValue([]);

    await request(app).get('/api/buscas-salvas');

    const where = mockPrisma.buscaSalva.findMany.mock.calls[0][0].where;
    expect(where.usuarioId).toBe('u1');
  });
});

// ---------------------------------------------------------------------------
// DELETE /api/buscas-salvas/:id
// ---------------------------------------------------------------------------

describe('DELETE /api/buscas-salvas/:id', () => {
  it('deletes own saved search', async () => {
    mockPrisma.buscaSalva.findUnique.mockResolvedValue({ id: 'b1', usuarioId: 'u1' });
    mockPrisma.buscaSalva.delete.mockResolvedValue({});

    const res = await request(app).delete('/api/buscas-salvas/b1');
    expect(res.status).toBe(204);
  });

  it('returns 404 for non-existent search', async () => {
    mockPrisma.buscaSalva.findUnique.mockResolvedValue(null);

    const res = await request(app).delete('/api/buscas-salvas/xxx');
    expect(res.status).toBe(404);
  });

  it('returns 403 for other user search', async () => {
    mockPrisma.buscaSalva.findUnique.mockResolvedValue({ id: 'b1', usuarioId: 'other' });

    const res = await request(app).delete('/api/buscas-salvas/b1');
    expect(res.status).toBe(403);
  });
});
