import { describe, it, expect, vi, beforeEach } from 'vitest';
import express, { Express } from 'express';
import request from 'supertest';

/**
 * Unit tests for the /api/auth routes.
 *
 * Uses supertest to drive an in-memory Express app with the auth router
 * mounted. Prisma is mocked so no database is needed.
 */

// ---------------------------------------------------------------------------
// Mocks — vi.hoisted() ensures these are available before vi.mock factories
// ---------------------------------------------------------------------------

const { mockPrisma } = vi.hoisted(() => ({
  mockPrisma: {
    usuario: {
      findUnique: vi.fn(),
      create: vi.fn(),
    },
  },
}));

vi.mock('../../src/lib/prisma.js', () => ({ prisma: mockPrisma }));

vi.mock('../../src/lib/logger.js', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn().mockReturnThis(),
  },
}));

vi.mock('../../src/config/env.js', () => ({
  env: {
    JWT_SECRET: 'test-jwt-secret-32-chars-minimum!!',
    JWT_REFRESH_SECRET: 'test-refresh-secret-32-chars!!!!',
    JWT_EXPIRES_IN: '15m',
    JWT_REFRESH_EXPIRES_IN: '7d',
    NODE_ENV: 'test',
    PORT: 3099,
    CORS_ORIGIN: '*',
    DATABASE_URL: 'postgresql://test:test@localhost:5432/test',
    REDIS_URL: 'redis://localhost:6379',
    PNCP_API_BASE: 'https://pncp.gov.br/api/consulta',
    QUERIDO_DIARIO_API_BASE: 'https://queridodiario.ok.org.br/api',
    SCRAPING_CONCURRENCY: 1,
    SCRAPING_RATE_LIMIT_MS: 0,
    LOG_LEVEL: 'silent',
  },
}));

import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import cookieParser from 'cookie-parser';
import { authRouter } from '../../src/api/routes/auth.js';
import { errorHandler } from '../../src/api/middleware/error-handler.js';

// ---------------------------------------------------------------------------
// App setup
// ---------------------------------------------------------------------------

let app: Express;

beforeEach(() => {
  app = express();
  app.use(express.json());
  app.use(cookieParser());
  app.use('/api/auth', authRouter);
  app.use(errorHandler);
  vi.clearAllMocks();
});

/** Verdadeiro se o Set-Cookie da resposta inclui o refresh token httpOnly. */
function hasRefreshCookie(res: request.Response): boolean {
  const cookies = res.headers['set-cookie'] ?? [];
  return cookies.some((c) => c.startsWith('refreshToken=') && /httponly/i.test(c));
}

// ---------------------------------------------------------------------------
// POST /api/auth/register
// ---------------------------------------------------------------------------

describe('POST /api/auth/register', () => {
  it('creates user and returns tokens', async () => {
    mockPrisma.usuario.findUnique.mockResolvedValue(null);
    mockPrisma.usuario.create.mockResolvedValue({
      id: 'u1',
      email: 'test@test.com',
      nome: 'Test User',
      empresa: 'ACME',
      cnpj: null,
    });

    const res = await request(app)
      .post('/api/auth/register')
      .send({ email: 'test@test.com', nome: 'Test User', senha: '123456', empresa: 'ACME' });

    expect(res.status).toBe(201);
    expect(res.body.user).toBeDefined();
    expect(res.body.user.email).toBe('test@test.com');
    expect(res.body.accessToken).toBeDefined();
    // Refresh token sai em cookie httpOnly, nao no corpo.
    expect(res.body.refreshToken).toBeUndefined();
    expect(hasRefreshCookie(res)).toBe(true);
  });

  it('returns 409 when email is already registered', async () => {
    mockPrisma.usuario.findUnique.mockResolvedValue({ id: 'existing' });

    const res = await request(app)
      .post('/api/auth/register')
      .send({ email: 'dup@test.com', nome: 'Dup', senha: '123456' });

    expect(res.status).toBe(409);
    expect(res.body.error).toContain('Email já cadastrado');
  });

  it('returns 400 for invalid email', async () => {
    const res = await request(app)
      .post('/api/auth/register')
      .send({ email: 'bad', nome: 'Test', senha: '123456' });

    expect(res.status).toBe(400);
  });

  it('returns 400 when senha is too short', async () => {
    const res = await request(app)
      .post('/api/auth/register')
      .send({ email: 'a@b.com', nome: 'Test', senha: '12' });

    expect(res.status).toBe(400);
  });
});

// ---------------------------------------------------------------------------
// POST /api/auth/login
// ---------------------------------------------------------------------------

describe('POST /api/auth/login', () => {
  it('returns tokens for valid credentials', async () => {
    const hashedPw = await bcrypt.hash('123456', 10);
    mockPrisma.usuario.findUnique.mockResolvedValue({
      id: 'u1',
      email: 'user@test.com',
      nome: 'User',
      empresa: null,
      cnpj: null,
      senha: hashedPw,
    });

    const res = await request(app)
      .post('/api/auth/login')
      .send({ email: 'user@test.com', senha: '123456' });

    expect(res.status).toBe(200);
    expect(res.body.accessToken).toBeDefined();
    // Refresh token sai em cookie httpOnly, nao no corpo.
    expect(res.body.refreshToken).toBeUndefined();
    expect(hasRefreshCookie(res)).toBe(true);
    expect(res.body.user.email).toBe('user@test.com');
  });

  it('returns 401 for non-existent user', async () => {
    mockPrisma.usuario.findUnique.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/auth/login')
      .send({ email: 'ghost@test.com', senha: '123456' });

    expect(res.status).toBe(401);
  });

  it('returns 401 for wrong password', async () => {
    const hashedPw = await bcrypt.hash('correct', 10);
    mockPrisma.usuario.findUnique.mockResolvedValue({
      id: 'u1', email: 'user@test.com', nome: 'User', empresa: null, cnpj: null, senha: hashedPw,
    });

    const res = await request(app)
      .post('/api/auth/login')
      .send({ email: 'user@test.com', senha: 'wrong' });

    expect(res.status).toBe(401);
  });
});

// ---------------------------------------------------------------------------
// POST /api/auth/refresh
// ---------------------------------------------------------------------------

describe('POST /api/auth/refresh', () => {
  it('returns a new access token and rotates the cookie for a valid refresh token', async () => {
    const refreshToken = jwt.sign(
      { userId: 'u1', email: 'test@test.com' },
      'test-refresh-secret-32-chars!!!!',
      { expiresIn: '7d' },
    );
    // /refresh agora confere se a conta ainda existe antes de re-emitir.
    mockPrisma.usuario.findUnique.mockResolvedValue({ id: 'u1', email: 'test@test.com' });

    const res = await request(app)
      .post('/api/auth/refresh')
      .set('Cookie', `refreshToken=${refreshToken}`);

    expect(res.status).toBe(200);
    expect(res.body.accessToken).toBeDefined();
    // Refresh token novo vai no cookie rotacionado, nao no corpo.
    expect(res.body.refreshToken).toBeUndefined();
    expect(hasRefreshCookie(res)).toBe(true);
  });

  it('returns 401 when the refresh token belongs to a deleted account', async () => {
    const refreshToken = jwt.sign(
      { userId: 'gone', email: 'gone@test.com' },
      'test-refresh-secret-32-chars!!!!',
      { expiresIn: '7d' },
    );
    mockPrisma.usuario.findUnique.mockResolvedValue(null);

    const res = await request(app)
      .post('/api/auth/refresh')
      .set('Cookie', `refreshToken=${refreshToken}`);

    expect(res.status).toBe(401);
  });

  it('returns 401 for an invalid refresh token', async () => {
    const res = await request(app)
      .post('/api/auth/refresh')
      .set('Cookie', 'refreshToken=garbage');

    expect(res.status).toBe(401);
  });

  it('returns 401 when the refresh cookie is missing', async () => {
    const res = await request(app).post('/api/auth/refresh');

    expect(res.status).toBe(401);
  });
});

// ---------------------------------------------------------------------------
// POST /api/auth/logout
// ---------------------------------------------------------------------------

describe('POST /api/auth/logout', () => {
  it('clears the refresh cookie and returns 204', async () => {
    const res = await request(app).post('/api/auth/logout');

    expect(res.status).toBe(204);
    // clearCookie emite um Set-Cookie com refreshToken vazio/expirado.
    const cookies = res.headers['set-cookie'] ?? [];
    expect(cookies.some((c) => c.startsWith('refreshToken='))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// GET /api/auth/me
// ---------------------------------------------------------------------------

describe('GET /api/auth/me', () => {
  it('returns user profile for valid access token', async () => {
    const accessToken = jwt.sign(
      { userId: 'u1', email: 'test@test.com' },
      'test-jwt-secret-32-chars-minimum!!',
      { expiresIn: '15m' },
    );

    mockPrisma.usuario.findUnique.mockResolvedValue({
      id: 'u1',
      email: 'test@test.com',
      nome: 'Test',
      empresa: 'ACME',
      cnpj: null,
      criadoEm: new Date(),
      atualizadoEm: new Date(),
    });

    const res = await request(app)
      .get('/api/auth/me')
      .set('Authorization', `Bearer ${accessToken}`);

    expect(res.status).toBe(200);
    expect(res.body.email).toBe('test@test.com');
  });

  it('returns 401 without token', async () => {
    const res = await request(app).get('/api/auth/me');
    expect(res.status).toBe(401);
  });

  it('returns 401 with expired token', async () => {
    const expired = jwt.sign(
      { userId: 'u1', email: 'test@test.com' },
      'test-jwt-secret-32-chars-minimum!!',
      { expiresIn: '0s' },
    );

    const res = await request(app)
      .get('/api/auth/me')
      .set('Authorization', `Bearer ${expired}`);

    expect(res.status).toBe(401);
  });
});
