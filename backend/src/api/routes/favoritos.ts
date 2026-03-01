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

const createFavoritoSchema = z.object({
  licitacaoId: z.string().min(1, 'licitacaoId é obrigatório'),
  notas: z.string().optional(),
  tags: z.array(z.string()).default([]),
});

const listQuerySchema = z.object({
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(20),
});

// ---------------------------------------------------------------------------
// POST / - Add favorite (upsert)
// ---------------------------------------------------------------------------

router.post('/', asyncHandler(async (req, res) => {
  const data = createFavoritoSchema.parse(req.body);
  const usuarioId = req.user!.userId;

  // Verify the licitacao exists
  const licitacao = await prisma.licitacao.findUnique({
    where: { id: data.licitacaoId },
    select: { id: true },
  });
  if (!licitacao) {
    throw new AppError(404, 'Licitação não encontrada');
  }

  const favorito = await prisma.favorito.upsert({
    where: {
      usuarioId_licitacaoId: {
        usuarioId,
        licitacaoId: data.licitacaoId,
      },
    },
    update: {
      notas: data.notas,
      tags: data.tags,
    },
    create: {
      usuarioId,
      licitacaoId: data.licitacaoId,
      notas: data.notas,
      tags: data.tags,
    },
    include: {
      licitacao: {
        select: {
          id: true,
          objeto: true,
          objetoResumido: true,
          orgao: true,
          modalidade: true,
          status: true,
          dataAbertura: true,
          valorEstimado: true,
        },
      },
    },
  });

  logger.info({ favoritoId: favorito.id, usuarioId }, 'Favorito adicionado');
  res.status(201).json(favorito);
}));

// ---------------------------------------------------------------------------
// GET / - List favorites with licitacao data
// ---------------------------------------------------------------------------

router.get('/', asyncHandler(async (req, res) => {
  const { page, pageSize } = listQuerySchema.parse(req.query);
  const usuarioId = req.user!.userId;
  const skip = (page - 1) * pageSize;

  const [data, total] = await Promise.all([
    prisma.favorito.findMany({
      where: { usuarioId },
      orderBy: { criadoEm: 'desc' },
      skip,
      take: pageSize,
      include: {
        licitacao: {
          select: {
            id: true,
            numeroEdital: true,
            modalidade: true,
            tipo: true,
            orgao: true,
            orgaoSigla: true,
            esfera: true,
            uf: true,
            municipio: true,
            objeto: true,
            objetoResumido: true,
            valorEstimado: true,
            dataPublicacao: true,
            dataAbertura: true,
            status: true,
            segmento: true,
            fonteOrigem: true,
            urlOrigem: true,
          },
        },
      },
    }),
    prisma.favorito.count({ where: { usuarioId } }),
  ]);

  const totalPages = Math.ceil(total / pageSize);

  res.json({
    data,
    pagination: {
      page,
      pageSize,
      total,
      totalPages,
    },
  });
}));

// ---------------------------------------------------------------------------
// DELETE /:id - Remove favorite
// ---------------------------------------------------------------------------

router.delete('/:id', asyncHandler(async (req, res) => {
  const id = req.params.id as string;
  const usuarioId = req.user!.userId;

  const existing = await prisma.favorito.findUnique({ where: { id } });
  if (!existing) {
    throw new AppError(404, 'Favorito não encontrado');
  }
  if (existing.usuarioId !== usuarioId) {
    throw new AppError(403, 'Sem permissão para excluir este favorito');
  }

  await prisma.favorito.delete({ where: { id } });

  logger.info({ favoritoId: id, usuarioId }, 'Favorito removido');
  res.status(204).send();
}));

export { router as favoritosRouter };
