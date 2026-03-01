import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
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

// Middleware
app.use(helmet());
app.use(cors({ origin: env.CORS_ORIGIN, credentials: true }));
app.use(compression());
app.use(express.json({ limit: '10mb' }));
app.use(rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
}));

// Health check
app.get('/api/health', async (_req, res) => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  } catch {
    res.status(503).json({ status: 'error', message: 'Database unavailable' });
  }
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
  logger.info(`LicitaBrasil API running on port ${env.PORT}`);
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
