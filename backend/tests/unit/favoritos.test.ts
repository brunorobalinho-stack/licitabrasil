import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    licitacao: {
      findUnique: vi.fn(),
    },
    favorito: {
      upsert: vi.fn(),
      findMany: vi.fn(),
      findUnique: vi.fn(),
      count: vi.fn(),
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

import { favoritosRouter } from '../../src/api/routes/favoritos.js';
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
  app.use('/api/favoritos', favoritosRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// POST /api/favoritos
// ---------------------------------------------------------------------------

describe('POST /api/favoritos', () => {
  it('creates a favorite (upsert)', async () => {
    mockPrisma.licitacao.findUnique.mockResolvedValue({ id: 'lic1' });
    mockPrisma.favorito.upsert.mockResolvedValue({
      id: 'f1', usuarioId: 'u1', licitacaoId: 'lic1',
      licitacao: { id: 'lic1', objeto: 'Test' },
    });

    const res = await request(app).post('/api/favoritos').send({ licitacaoId: 'lic1' });

    expect(res.status).toBe(201);
    expect(res.body.id).toBe('f1');
  });

  it('returns 404 when licitacao does not exist', async () => {
    mockPrisma.licitacao.findUnique.mockResolvedValue(null);

    const res = await request(app).post('/api/favoritos').send({ licitacaoId: 'xxx' });
    expect(res.status).toBe(404);
  });

  it('returns 400 when licitacaoId is missing', async () => {
    const res = await request(app).post('/api/favoritos').send({});
    expect(res.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// GET /api/favoritos
// ---------------------------------------------------------------------------

describe('GET /api/favoritos', () => {
  it('returns paginated favorites with licitacao data', async () => {
    mockPrisma.favorito.findMany.mockResolvedValue([{ id: 'f1', licitacao: { id: 'lic1' } }]);
    mockPrisma.favorito.count.mockResolvedValue(1);

    const res = await request(app).get('/api/favoritos');

    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(1);
    expect(res.body.pagination.total).toBe(1);
  });

  it('respects pagination params', async () => {
    mockPrisma.favorito.findMany.mockResolvedValue([]);
    mockPrisma.favorito.count.mockResolvedValue(30);

    await request(app).get('/api/favoritos?page=2&pageSize=10');

    const call = mockPrisma.favorito.findMany.mock.calls[0][0];
    expect(call.skip).toBe(10);
    expect(call.take).toBe(10);
  });
});

// ---------------------------------------------------------------------------
// DELETE /api/favoritos/:id
// ---------------------------------------------------------------------------

describe('DELETE /api/favoritos/:id', () => {
  it('deletes own favorite', async () => {
    mockPrisma.favorito.findUnique.mockResolvedValue({ id: 'f1', usuarioId: 'u1' });
    mockPrisma.favorito.delete.mockResolvedValue({});

    const res = await request(app).delete('/api/favoritos/f1');
    expect(res.status).toBe(204);
  });

  it('returns 404 for non-existent favorite', async () => {
    mockPrisma.favorito.findUnique.mockResolvedValue(null);

    const res = await request(app).delete('/api/favoritos/xxx');
    expect(res.status).toBe(404);
  });

  it('returns 403 for other user favorite', async () => {
    mockPrisma.favorito.findUnique.mockResolvedValue({ id: 'f1', usuarioId: 'other' });

    const res = await request(app).delete('/api/favoritos/f1');
    expect(res.status).toBe(403);
  });
});
