import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import { prisma } from '../../lib/prisma.js';
import { logger } from '../../lib/logger.js';
import { AppError } from '../middleware/error-handler.js';

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
// Validation schemas
// ---------------------------------------------------------------------------

const createBuscaSchema = z.object({
  nome: z.string().min(1, 'Nome é obrigatório').max(200),
  filtros: z.record(z.unknown()).refine(
    (val) => Object.keys(val).length > 0,
    'Filtros não podem estar vazios',
  ),
});

// ---------------------------------------------------------------------------
// POST / - Save search
// ---------------------------------------------------------------------------
/** @openapi
 * /buscas-salvas:
 *   post:
 *     tags: [Buscas Salvas]
 *     summary: Salvar busca
 *     security:
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [nome, filtros]
 *             properties:
 *               nome: { type: string }
 *               filtros: { type: object }
 *     responses:
 *       201:
 *         description: Busca salva
 *   get:
 *     tags: [Buscas Salvas]
 *     summary: Listar buscas salvas do usuário
 *     security:
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Array de buscas salvas
 */
/** @openapi
 * /buscas-salvas/{id}:
 *   delete:
 *     tags: [Buscas Salvas]
 *     summary: Excluir busca salva
 *     security:
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       204:
 *         description: Excluído
 */
router.post('/', asyncHandler(async (req, res) => {
  const data = createBuscaSchema.parse(req.body);
  const usuarioId = req.user!.userId;

  const busca = await prisma.buscaSalva.create({
    data: {
      usuarioId,
      nome: data.nome,
      filtros: data.filtros as Prisma.InputJsonValue,
    },
  });

  logger.info({ buscaId: busca.id, usuarioId }, 'Busca salva criada');
  res.status(201).json(busca);
}));

// ---------------------------------------------------------------------------
// GET / - List saved searches for current user
// ---------------------------------------------------------------------------

router.get('/', asyncHandler(async (req, res) => {
  const usuarioId = req.user!.userId;

  const buscas = await prisma.buscaSalva.findMany({
    where: { usuarioId },
    orderBy: { criadoEm: 'desc' },
  });

  res.json(buscas);
}));

// ---------------------------------------------------------------------------
// DELETE /:id - Delete saved search
// ---------------------------------------------------------------------------

router.delete('/:id', asyncHandler(async (req, res) => {
  const id = req.params.id as string;
  const usuarioId = req.user!.userId;

  const existing = await prisma.buscaSalva.findUnique({ where: { id } });
  if (!existing) {
    throw new AppError(404, 'Busca salva não encontrada');
  }
  if (existing.usuarioId !== usuarioId) {
    throw new AppError(403, 'Sem permissão para excluir esta busca salva');
  }

  await prisma.buscaSalva.delete({ where: { id } });

  logger.info({ buscaId: id, usuarioId }, 'Busca salva excluída');
  res.status(204).send();
}));

export { router as buscasSalvasRouter };
