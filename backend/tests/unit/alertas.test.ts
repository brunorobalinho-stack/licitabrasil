import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    alerta: {
      create: vi.fn(),
      findMany: vi.fn(),
      findUnique: vi.fn(),
      count: vi.fn(),
      update: vi.fn(),
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

import { alertasRouter } from '../../src/api/routes/alertas.js';
import { errorHandler } from '../../src/api/middleware/error-handler.js';

let app: Express;

const fakeAuth = (req: express.Request, _res: express.Response, next: express.NextFunction) => {
  req.user = { userId: 'u1', email: 'test@test.com' };
  next();
};

const validBody = {
  palavrasChave: ['software'],
  frequencia: 'DIARIO',
  canalNotificacao: ['EMAIL'],
};

beforeEach(() => {
  app = express();
  app.use(express.json());
  app.use(fakeAuth);
  app.use('/api/alertas', alertasRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// POST /api/alertas
// ---------------------------------------------------------------------------

describe('POST /api/alertas', () => {
  it('creates an alert', async () => {
    mockPrisma.alerta.create.mockResolvedValue({ id: 'a1', ...validBody, usuarioId: 'u1' });

    const res = await request(app).post('/api/alertas').send(validBody);

    expect(res.status).toBe(201);
    expect(res.body.id).toBe('a1');
    expect(mockPrisma.alerta.create).toHaveBeenCalledOnce();
  });

  it('returns 400 when palavrasChave is empty', async () => {
    const res = await request(app).post('/api/alertas').send({ ...validBody, palavrasChave: [] });
    expect(res.status).toBe(400);
  });

  it('returns 400 when frequencia is missing', async () => {
    const res = await request(app).post('/api/alertas').send({ palavrasChave: ['test'], canalNotificacao: ['EMAIL'] });
    expect(res.status).toBe(400);
  });

  it('returns 400 when canalNotificacao is empty', async () => {
    const res = await request(app).post('/api/alertas').send({ ...validBody, canalNotificacao: [] });
    expect(res.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// GET /api/alertas
// ---------------------------------------------------------------------------

describe('GET /api/alertas', () => {
  it('returns paginated alerts for user', async () => {
    mockPrisma.alerta.findMany.mockResolvedValue([{ id: 'a1' }]);
    mockPrisma.alerta.count.mockResolvedValue(1);

    const res = await request(app).get('/api/alertas');

    expect(res.status).toBe(200);
    expect(res.body.data).toHaveLength(1);
    expect(res.body.pagination.total).toBe(1);
  });

  it('respects page and pageSize', async () => {
    mockPrisma.alerta.findMany.mockResolvedValue([]);
    mockPrisma.alerta.count.mockResolvedValue(50);

    await request(app).get('/api/alertas?page=2&pageSize=10');

    const call = mockPrisma.alerta.findMany.mock.calls[0][0];
    expect(call.skip).toBe(10);
    expect(call.take).toBe(10);
  });
});

// ---------------------------------------------------------------------------
// PUT /api/alertas/:id
// ---------------------------------------------------------------------------

describe('PUT /api/alertas/:id', () => {
  it('updates own alert', async () => {
    mockPrisma.alerta.findUnique.mockResolvedValue({ id: 'a1', usuarioId: 'u1' });
    mockPrisma.alerta.update.mockResolvedValue({ id: 'a1', ativo: false });

    const res = await request(app).put('/api/alertas/a1').send({ ativo: false });

    expect(res.status).toBe(200);
    expect(mockPrisma.alerta.update).toHaveBeenCalledOnce();
  });

  it('returns 404 for non-existent alert', async () => {
    mockPrisma.alerta.findUnique.mockResolvedValue(null);

    const res = await request(app).put('/api/alertas/xxx').send({ ativo: false });
    expect(res.status).toBe(404);
  });

  it('returns 403 for other user alert', async () => {
    mockPrisma.alerta.findUnique.mockResolvedValue({ id: 'a1', usuarioId: 'other' });

    const res = await request(app).put('/api/alertas/a1').send({ ativo: false });
    expect(res.status).toBe(403);
  });
});

// ---------------------------------------------------------------------------
// DELETE /api/alertas/:id
// ---------------------------------------------------------------------------

describe('DELETE /api/alertas/:id', () => {
  it('deletes own alert', async () => {
    mockPrisma.alerta.findUnique.mockResolvedValue({ id: 'a1', usuarioId: 'u1' });
    mockPrisma.alerta.delete.mockResolvedValue({});

    const res = await request(app).delete('/api/alertas/a1');
    expect(res.status).toBe(204);
  });

  it('returns 404 for non-existent alert', async () => {
    mockPrisma.alerta.findUnique.mockResolvedValue(null);

    const res = await request(app).delete('/api/alertas/xxx');
    expect(res.status).toBe(404);
  });

  it('returns 403 for other user alert', async () => {
    mockPrisma.alerta.findUnique.mockResolvedValue({ id: 'a1', usuarioId: 'other' });

    const res = await request(app).delete('/api/alertas/a1');
    expect(res.status).toBe(403);
  });
});
