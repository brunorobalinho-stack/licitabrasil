import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import cookieParser from 'cookie-parser';
import rateLimit from 'express-rate-limit';
import pinoHttp from 'pino-http';
import { env } from './config/env.js';
import { logger } from './lib/logger.js';
import { prisma } from './lib/prisma.js';
import { redis } from './lib/redis.js';
import { authRouter } from './api/routes/auth.js';
import { licitacoesRouter } from './api/routes/licitacoes.js';
import { alertasRouter } from './api/routes/alertas.js';
import { favoritosRouter } from './api/routes/favoritos.js';
import { buscasSalvasRouter } from './api/routes/buscas-salvas.js';
import { dashboardRouter } from './api/routes/dashboard.js';
import { fontesRouter } from './api/routes/fontes.js';
import { authMiddleware } from './api/middleware/auth.js';
import { errorHandler } from './api/middleware/error-handler.js';

const app = express();

// Request logging
app.use(pinoHttp({ logger }));

// CORS: env var can be a single domain or a comma-separated list of domains,
// so staging and prod can share the same image without rebuild.
const corsOrigins = env.CORS_ORIGIN.split(',').map((s) => s.trim()).filter(Boolean);
const corsOrigin = corsOrigins.length <= 1 ? (corsOrigins[0] ?? false) : corsOrigins;

// Middleware
app.use(helmet());
app.use(cors({ origin: corsOrigin, credentials: true }));
app.use(compression());
// Le o cookie httpOnly do refresh token (rota /api/auth). O token nao
// fica mais acessivel ao JS do navegador -- fora do alcance de XSS.
app.use(cookieParser());
// Body limit kept tight: this API only receives filter/query bodies.
// 100kb is plenty and closes the DoS vector that 10mb left open.
app.use(express.json({ limit: '100kb' }));
app.use(rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
}));

// Health check (tests Postgres AND Redis)
app.get('/api/health', async (_req, res) => {
  const checks: Record<string, boolean> = { db: false, redis: false };

  try {
    await prisma.$queryRaw`SELECT 1`;
    checks.db = true;
  } catch {
    /* keep false */
  }

  try {
    const pong = await redis.ping();
    checks.redis = pong === 'PONG';
  } catch {
    /* keep false */
  }

  const healthy = checks.db && checks.redis;
  res.status(healthy ? 200 : 503).json({
    status: healthy ? 'ok' : 'error',
    checks,
    timestamp: new Date().toISOString(),
  });
});

// Routes
app.use('/api/auth', authRouter);
app.use('/api/licitacoes', licitacoesRouter);
app.use('/api/alertas', authMiddleware, alertasRouter);
app.use('/api/favoritos', authMiddleware, favoritosRouter);
app.use('/api/buscas-salvas', authMiddleware, buscasSalvasRouter);
app.use('/api/dashboard', dashboardRouter);
app.use('/api/fontes', fontesRouter);

// Error handler
app.use(errorHandler);

const server = app.listen(env.PORT, () => {
  logger.info({ corsOrigins }, `LicitaBrasil API running on port ${env.PORT}`);
});

// Graceful shutdown
const shutdown = async () => {
  logger.info('Shutting down...');
  server.close();
  await prisma.$disconnect();
  redis.disconnect();
  process.exit(0);
};
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);

export { app };
