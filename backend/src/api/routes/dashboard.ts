import { Router, Request, Response, NextFunction } from 'express';
import { prisma } from '../../lib/prisma.js';
import { cache } from '../../lib/redis.js';
import { logger } from '../../lib/logger.js';

const router = Router();

// ---------------------------------------------------------------------------
// Async handler wrapper
// ---------------------------------------------------------------------------

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;

function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function startOfDay(date: Date): Date {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  return d;
}

function startOfWeek(date: Date): Date {
  const d = new Date(date);
  const day = d.getDay();
  // Monday as start of week (Brazilian convention)
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  d.setDate(diff);
  d.setHours(0, 0, 0, 0);
  return d;
}

function endOfWeek(date: Date): Date {
  const start = startOfWeek(date);
  const end = new Date(start);
  end.setDate(end.getDate() + 6);
  end.setHours(23, 59, 59, 999);
  return end;
}

// ---------------------------------------------------------------------------
// GET /resumo - Summary statistics
// ---------------------------------------------------------------------------
/** @openapi
 * /dashboard/resumo:
 *   get:
 *     tags: [Dashboard]
 *     summary: Resumo semanal (novas hoje, abertas, encerradas, volume)
 *     responses:
 *       200:
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/DashboardResumo'
 */
router.get('/resumo', asyncHandler(async (_req, res) => {
  const cacheKey = 'dashboard:resumo';

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const now = new Date();
  const todayStart = startOfDay(now);
  const weekStart = startOfWeek(now);
  const weekEnd = endOfWeek(now);

  const [novasHoje, abertasEstaSemana, encerradasEstaSemana, volumeTotal] = await Promise.all([
    prisma.licitacao.count({
      where: {
        criadoEm: { gte: todayStart },
      },
    }),
    prisma.licitacao.count({
      where: {
        status: 'ABERTA',
        dataAbertura: {
          gte: weekStart,
          lte: weekEnd,
        },
      },
    }),
    prisma.licitacao.count({
      where: {
        status: 'ENCERRADA',
        dataEncerramento: {
          gte: weekStart,
          lte: weekEnd,
        },
      },
    }),
    prisma.licitacao.aggregate({
      where: { status: 'ABERTA' },
      _sum: { valorEstimado: true },
    }),
  ]);

  const result = {
    novasHoje,
    abertasEstaSemana,
    encerradasEstaSemana,
    volumeTotalAbertas: volumeTotal._sum.valorEstimado,
  };

  await cache.set(cacheKey, result, 300); // 5 minutes
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /por-estado - Count by UF
// ---------------------------------------------------------------------------
/** @openapi
 * /dashboard/por-estado:
 *   get:
 *     tags: [Dashboard]
 *     summary: Contagem de licitações por UF
 *     responses:
 *       200:
 *         description: Array [{uf, count}]
 */
router.get('/por-estado', asyncHandler(async (_req, res) => {
  const cacheKey = 'dashboard:por-estado';

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const grouped = await prisma.licitacao.groupBy({
    by: ['uf'],
    _count: { id: true },
    where: { uf: { not: null } },
    orderBy: { _count: { id: 'desc' } },
  });

  const result = grouped.map((item) => ({
    uf: item.uf,
    count: item._count.id,
  }));

  await cache.set(cacheKey, result, 900); // 15 minutes
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /por-modalidade - Count by modalidade
// ---------------------------------------------------------------------------
/** @openapi
 * /dashboard/por-modalidade:
 *   get:
 *     tags: [Dashboard]
 *     summary: Contagem de licitações por modalidade
 *     responses:
 *       200:
 *         description: Array [{modalidade, count}]
 */
router.get('/por-modalidade', asyncHandler(async (_req, res) => {
  const cacheKey = 'dashboard:por-modalidade';

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const grouped = await prisma.licitacao.groupBy({
    by: ['modalidade'],
    _count: { id: true },
    orderBy: { _count: { id: 'desc' } },
  });

  const result = grouped.map((item) => ({
    modalidade: item.modalidade,
    count: item._count.id,
  }));

  await cache.set(cacheKey, result, 900); // 15 minutes
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /tendencias - Publications per day for last 30 days
// ---------------------------------------------------------------------------
/** @openapi
 * /dashboard/tendencias:
 *   get:
 *     tags: [Dashboard]
 *     summary: Publicações por dia nos últimos 30 dias
 *     responses:
 *       200:
 *         description: Array [{date, count}]
 */
router.get('/tendencias', asyncHandler(async (_req, res) => {
  const cacheKey = 'dashboard:tendencias';

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const result = await prisma.$queryRaw<Array<{ date: string; count: bigint }>>`
    SELECT DATE_TRUNC('day', "dataPublicacao") as date, COUNT(*) as count
    FROM "Licitacao"
    WHERE "dataPublicacao" >= NOW() - INTERVAL '30 days'
    GROUP BY date
    ORDER BY date ASC
  `;

  // Convert BigInt count to number for JSON serialization
  const formatted = result.map((row) => ({
    date: row.date,
    count: Number(row.count),
  }));

  await cache.set(cacheKey, formatted, 900); // 15 minutes
  res.json(formatted);
}));

export { router as dashboardRouter };
