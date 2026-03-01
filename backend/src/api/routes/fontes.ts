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
// GET /status - List all FonteDados with health status
// ---------------------------------------------------------------------------

router.get('/status', asyncHandler(async (_req, res) => {
  const fontes = await prisma.fonteDados.findMany({
    orderBy: { nome: 'asc' },
  });

  const now = new Date();

  const result = fontes.map((fonte) => {
    // A source is considered healthy when:
    // 1. It has had a successful collection
    // 2. The last success is more recent than the last failure (or no failure)
    // 3. The last success occurred within 2x the configured interval
    const maxAgeMs = fonte.intervaloMinutos * 2 * 60 * 1000;
    const successRecent = fonte.ultimoSucesso
      ? now.getTime() - fonte.ultimoSucesso.getTime() <= maxAgeMs
      : false;
    const successAfterFailure = fonte.ultimoSucesso && fonte.ultimaFalha
      ? fonte.ultimoSucesso > fonte.ultimaFalha
      : fonte.ultimoSucesso !== null;
    const healthy = successRecent && successAfterFailure;

    return {
      id: fonte.id,
      nome: fonte.nome,
      url: fonte.url,
      tipo: fonte.tipo,
      esfera: fonte.esfera,
      ativo: fonte.ativo,
      ultimaColeta: fonte.ultimaColeta,
      ultimoSucesso: fonte.ultimoSucesso,
      ultimaFalha: fonte.ultimaFalha,
      totalColetados: fonte.totalColetados,
      totalErros: fonte.totalErros,
      intervaloMinutos: fonte.intervaloMinutos,
      healthy,
    };
  });

  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /cobertura - Coverage map: counts by esfera and by UF
// ---------------------------------------------------------------------------

router.get('/cobertura', asyncHandler(async (_req, res) => {
  const cacheKey = 'fontes:cobertura';

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const [byEsfera, byUf] = await Promise.all([
    prisma.licitacao.groupBy({
      by: ['esfera'],
      _count: { id: true },
    }),
    prisma.licitacao.groupBy({
      by: ['uf'],
      _count: { id: true },
      where: { uf: { not: null } },
    }),
  ]);

  const esferaCounts: Record<string, number> = {
    federal: 0,
    estadual: 0,
    municipal: 0,
  };
  for (const item of byEsfera) {
    esferaCounts[item.esfera.toLowerCase()] = item._count.id;
  }

  const porEstado: Record<string, number> = {};
  for (const item of byUf) {
    if (item.uf) {
      porEstado[item.uf] = item._count.id;
    }
  }

  const result = {
    federal: esferaCounts.federal,
    estadual: esferaCounts.estadual,
    municipal: esferaCounts.municipal,
    porEstado,
  };

  await cache.set(cacheKey, result, 1800); // 30 minutes
  res.json(result);
}));

export { router as fontesRouter };
