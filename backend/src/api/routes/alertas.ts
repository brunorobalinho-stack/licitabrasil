import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
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

const listQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(50).default(20),
});

const createAlertaSchema = z.object({
  palavrasChave: z.array(z.string().min(1)).min(1, 'Pelo menos uma palavra-chave é obrigatória'),
  modalidades: z.array(z.enum([
    'PREGAO_ELETRONICO', 'PREGAO_PRESENCIAL', 'CONCORRENCIA',
    'CONCORRENCIA_ELETRONICA', 'TOMADA_DE_PRECOS', 'CONVITE', 'CONCURSO',
    'LEILAO', 'DIALOGO_COMPETITIVO', 'DISPENSA', 'INEXIGIBILIDADE',
    'CREDENCIAMENTO', 'RDC', 'OUTRA',
  ])).default([]),
  esferas: z.array(z.enum(['FEDERAL', 'ESTADUAL', 'MUNICIPAL'])).default([]),
  estados: z.array(z.string().length(2)).default([]),
  municipios: z.array(z.string()).default([]),
  segmentos: z.array(z.string()).default([]),
  valorMinimo: z.number().min(0).optional(),
  valorMaximo: z.number().min(0).optional(),
  frequencia: z.enum(['TEMPO_REAL', 'DIARIO', 'SEMANAL']),
  canalNotificacao: z.array(z.string().min(1)).min(1, 'Pelo menos um canal de notificação é obrigatório'),
});

const updateAlertaSchema = createAlertaSchema.partial().extend({
  ativo: z.boolean().optional(),
});

// ---------------------------------------------------------------------------
// POST / - Create alert
// ---------------------------------------------------------------------------
/** @openapi
 * /alertas:
 *   post:
 *     tags: [Alertas]
 *     summary: Criar alerta de monitoramento
 *     security:
 *       - cookieAuth: []
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/CreateAlertaRequest'
 *     responses:
 *       201:
 *         description: Alerta criado
 *   get:
 *     tags: [Alertas]
 *     summary: Listar alertas do usuário
 *     security:
 *       - cookieAuth: []
 *     parameters:
 *       - in: query
 *         name: page
 *         schema: { type: integer, default: 1 }
 *       - in: query
 *         name: pageSize
 *         schema: { type: integer, default: 20 }
 *     responses:
 *       200:
 *         description: Lista paginada de alertas
 */
/** @openapi
 * /alertas/{id}:
 *   put:
 *     tags: [Alertas]
 *     summary: Atualizar alerta
 *     security:
 *       - cookieAuth: []
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200:
 *         description: Alerta atualizado
 *       404:
 *         description: Não encontrado
 *   delete:
 *     tags: [Alertas]
 *     summary: Excluir alerta
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
  const data = createAlertaSchema.parse(req.body);
  const usuarioId = req.user!.userId;

  const alerta = await prisma.alerta.create({
    data: {
      usuarioId,
      palavrasChave: data.palavrasChave,
      modalidades: data.modalidades,
      esferas: data.esferas,
      estados: data.estados,
      municipios: data.municipios,
      segmentos: data.segmentos,
      valorMinimo: data.valorMinimo,
      valorMaximo: data.valorMaximo,
      frequencia: data.frequencia,
      canalNotificacao: data.canalNotificacao,
      ativo: true,
      totalEnviados: 0,
    },
  });

  logger.info({ alertaId: alerta.id, usuarioId }, 'Alerta criado');
  res.status(201).json(alerta);
}));

// ---------------------------------------------------------------------------
// GET / - List alerts for current user
// ---------------------------------------------------------------------------

router.get('/', asyncHandler(async (req, res) => {
  const usuarioId = req.user!.userId;
  const { page, pageSize } = listQuerySchema.parse(req.query);
  const skip = (page - 1) * pageSize;

  const [alertas, total] = await Promise.all([
    prisma.alerta.findMany({
      where: { usuarioId },
      orderBy: { criadoEm: 'desc' },
      skip,
      take: pageSize,
      include: {
        _count: {
          select: { matches: true },
        },
      },
    }),
    prisma.alerta.count({ where: { usuarioId } }),
  ]);

  res.json({
    data: alertas,
    pagination: {
      page,
      pageSize,
      total,
      totalPages: Math.ceil(total / pageSize),
    },
  });
}));

// ---------------------------------------------------------------------------
// PUT /:id - Update alert
// ---------------------------------------------------------------------------

router.put('/:id', asyncHandler(async (req, res) => {
  const id = req.params.id as string;
  const usuarioId = req.user!.userId;
  const data = updateAlertaSchema.parse(req.body);

  const existing = await prisma.alerta.findUnique({ where: { id } });
  if (!existing) {
    throw new AppError(404, 'Alerta não encontrado');
  }
  if (existing.usuarioId !== usuarioId) {
    throw new AppError(403, 'Sem permissão para editar este alerta');
  }

  const alerta = await prisma.alerta.update({
    where: { id },
    data,
  });

  logger.info({ alertaId: id, usuarioId }, 'Alerta atualizado');
  res.json(alerta);
}));

// ---------------------------------------------------------------------------
// DELETE /:id - Delete alert
// ---------------------------------------------------------------------------

router.delete('/:id', asyncHandler(async (req, res) => {
  const id = req.params.id as string;
  const usuarioId = req.user!.userId;

  const existing = await prisma.alerta.findUnique({ where: { id } });
  if (!existing) {
    throw new AppError(404, 'Alerta não encontrado');
  }
  if (existing.usuarioId !== usuarioId) {
    throw new AppError(403, 'Sem permissão para excluir este alerta');
  }

  await prisma.alerta.delete({ where: { id } });

  logger.info({ alertaId: id, usuarioId }, 'Alerta excluído');
  res.status(204).send();
}));

export { router as alertasRouter };
