import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import crypto from 'crypto';
import { prisma } from '../../lib/prisma.js';
import { cache } from '../../lib/redis.js';
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
  q: z.string().optional(),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(20),
  esfera: z.enum(['FEDERAL', 'ESTADUAL', 'MUNICIPAL']).optional(),
  uf: z.string().length(2).optional(),
  municipio: z.string().optional(),
  modalidade: z.enum([
    'PREGAO_ELETRONICO', 'PREGAO_PRESENCIAL', 'CONCORRENCIA',
    'CONCORRENCIA_ELETRONICA', 'TOMADA_DE_PRECOS', 'CONVITE', 'CONCURSO',
    'LEILAO', 'DIALOGO_COMPETITIVO', 'DISPENSA', 'INEXIGIBILIDADE',
    'CREDENCIAMENTO', 'RDC', 'OUTRA',
  ]).optional(),
  tipo: z.enum([
    'COMPRA', 'SERVICO', 'OBRA', 'SERVICO_ENGENHARIA',
    'ALIENACAO', 'CONCESSAO', 'PERMISSAO', 'LOCACAO', 'OUTRO',
  ]).optional(),
  status: z.enum([
    'PUBLICADA', 'ABERTA', 'EM_ANDAMENTO', 'SUSPENSA', 'ADIADA',
    'ENCERRADA', 'ANULADA', 'REVOGADA', 'DESERTA', 'FRACASSADA',
    'HOMOLOGADA', 'ADJUDICADA',
  ]).optional(),
  segmento: z.string().optional(),
  orgao: z.string().optional(),
  valorMin: z.coerce.number().min(0).optional(),
  valorMax: z.coerce.number().min(0).optional(),
  dataPublicacaoInicio: z.string().datetime({ offset: true }).optional()
    .or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional()),
  dataPublicacaoFim: z.string().datetime({ offset: true }).optional()
    .or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional()),
  dataAberturaInicio: z.string().datetime({ offset: true }).optional()
    .or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional()),
  dataAberturaFim: z.string().datetime({ offset: true }).optional()
    .or(z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional()),
  fonteOrigem: z.string().optional(),
  ordenarPor: z.enum(['dataPublicacao', 'dataAbertura', 'valorEstimado', 'relevancia']).default('dataPublicacao'),
  ordem: z.enum(['asc', 'desc']).default('desc'),
});

const searchQuerySchema = z.object({
  q: z.string().min(1, 'Parâmetro de busca obrigatório'),
  page: z.coerce.number().int().min(1).default(1),
  pageSize: z.coerce.number().int().min(1).max(100).default(20),
});

const timelineQuerySchema = z.object({
  esfera: z.enum(['FEDERAL', 'ESTADUAL', 'MUNICIPAL']).optional(),
  uf: z.string().length(2).optional(),
  modalidade: z.enum([
    'PREGAO_ELETRONICO', 'PREGAO_PRESENCIAL', 'CONCORRENCIA',
    'CONCORRENCIA_ELETRONICA', 'TOMADA_DE_PRECOS', 'CONVITE', 'CONCURSO',
    'LEILAO', 'DIALOGO_COMPETITIVO', 'DISPENSA', 'INEXIGIBILIDADE',
    'CREDENCIAMENTO', 'RDC', 'OUTRA',
  ]).optional(),
  limit: z.coerce.number().int().min(1).max(200).default(50),
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function hashQuery(params: Record<string, unknown>): string {
  const sorted = JSON.stringify(params, Object.keys(params).sort());
  return crypto.createHash('sha256').update(sorted).digest('hex').slice(0, 16);
}

function buildWhereClause(params: z.infer<typeof listQuerySchema>): Prisma.LicitacaoWhereInput {
  const where: Prisma.LicitacaoWhereInput = {};

  if (params.q) {
    where.objeto = { contains: params.q, mode: 'insensitive' };
  }
  if (params.esfera) {
    where.esfera = params.esfera;
  }
  if (params.uf) {
    where.uf = params.uf.toUpperCase();
  }
  if (params.municipio) {
    where.municipio = { contains: params.municipio, mode: 'insensitive' };
  }
  if (params.modalidade) {
    where.modalidade = params.modalidade;
  }
  if (params.tipo) {
    where.tipo = params.tipo;
  }
  if (params.status) {
    where.status = params.status;
  }
  if (params.segmento) {
    where.segmento = { contains: params.segmento, mode: 'insensitive' };
  }
  if (params.orgao) {
    where.orgao = { contains: params.orgao, mode: 'insensitive' };
  }
  if (params.valorMin !== undefined || params.valorMax !== undefined) {
    where.valorEstimado = {};
    if (params.valorMin !== undefined) {
      where.valorEstimado.gte = params.valorMin;
    }
    if (params.valorMax !== undefined) {
      where.valorEstimado.lte = params.valorMax;
    }
  }
  if (params.dataPublicacaoInicio || params.dataPublicacaoFim) {
    where.dataPublicacao = {};
    if (params.dataPublicacaoInicio) {
      where.dataPublicacao.gte = new Date(params.dataPublicacaoInicio);
    }
    if (params.dataPublicacaoFim) {
      where.dataPublicacao.lte = new Date(params.dataPublicacaoFim);
    }
  }
  if (params.dataAberturaInicio || params.dataAberturaFim) {
    where.dataAbertura = {};
    if (params.dataAberturaInicio) {
      where.dataAbertura.gte = new Date(params.dataAberturaInicio);
    }
    if (params.dataAberturaFim) {
      where.dataAbertura.lte = new Date(params.dataAberturaFim);
    }
  }
  if (params.fonteOrigem) {
    where.fonteOrigem = params.fonteOrigem;
  }

  return where;
}

function buildOrderBy(
  ordenarPor: string,
  ordem: 'asc' | 'desc',
): Prisma.LicitacaoOrderByWithRelationInput {
  switch (ordenarPor) {
    case 'dataAbertura':
      return { dataAbertura: ordem };
    case 'valorEstimado':
      return { valorEstimado: ordem };
    case 'relevancia':
      // Relevance ordering falls back to dataPublicacao until full-text ranking is added
      return { dataPublicacao: ordem };
    case 'dataPublicacao':
    default:
      return { dataPublicacao: ordem };
  }
}

// ---------------------------------------------------------------------------
// GET / - List licitacoes with filters
// ---------------------------------------------------------------------------

router.get('/', asyncHandler(async (req, res) => {
  const params = listQuerySchema.parse(req.query);
  const cacheKey = `licitacoes:list:${hashQuery(params)}`;

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const where = buildWhereClause(params);
  const orderBy = buildOrderBy(params.ordenarPor, params.ordem);
  const skip = (params.page - 1) * params.pageSize;

  const [data, total] = await Promise.all([
    prisma.licitacao.findMany({
      where,
      orderBy,
      skip,
      take: params.pageSize,
      select: {
        id: true,
        numeroEdital: true,
        numeroProcesso: true,
        codigoPNCP: true,
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
        criadoEm: true,
      },
    }),
    prisma.licitacao.count({ where }),
  ]);

  const totalPages = Math.ceil(total / params.pageSize);
  const result = {
    data,
    pagination: {
      page: params.page,
      pageSize: params.pageSize,
      total,
      totalPages,
    },
  };

  await cache.set(cacheKey, result, 900); // 15 minutes
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /search - Full-text search
// ---------------------------------------------------------------------------

router.get('/search', asyncHandler(async (req, res) => {
  const params = searchQuerySchema.parse(req.query);
  const skip = (params.page - 1) * params.pageSize;
  const cacheKey = `licitacoes:search:${hashQuery(params)}`;

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  // Sanitise query for tsquery: replace spaces with & for AND semantics
  const tsQuery = params.q
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .map((term) => term.replace(/[^a-zA-Z0-9À-ÿ]/g, ''))
    .filter(Boolean)
    .join(' & ');

  let data: unknown[];
  let total: number;

  try {
    // Attempt full-text search using tsvector
    const countResult = await prisma.$queryRawUnsafe<[{ count: bigint }]>(
      `SELECT COUNT(*) as count FROM "Licitacao" WHERE "searchVector" @@ to_tsquery('portuguese', $1)`,
      tsQuery,
    );
    total = Number(countResult[0].count);

    data = await prisma.$queryRawUnsafe(
      `SELECT id, "numeroEdital", "numeroProcesso", "codigoPNCP",
              modalidade, tipo, orgao, "orgaoSigla", esfera, uf, municipio,
              objeto, "objetoResumido", "valorEstimado",
              "dataPublicacao", "dataAbertura", status, segmento,
              "fonteOrigem", "urlOrigem", "criadoEm",
              ts_rank("searchVector", to_tsquery('portuguese', $1)) AS rank
       FROM "Licitacao"
       WHERE "searchVector" @@ to_tsquery('portuguese', $1)
       ORDER BY rank DESC
       LIMIT $2 OFFSET $3`,
      tsQuery,
      params.pageSize,
      skip,
    );
  } catch (err) {
    // Fallback to ILIKE if searchVector is not populated or tsquery fails
    logger.warn({ err }, 'Full-text search fallback to ILIKE');

    const where: Prisma.LicitacaoWhereInput = {
      objeto: { contains: params.q, mode: 'insensitive' },
    };

    [data, total] = await Promise.all([
      prisma.licitacao.findMany({
        where,
        orderBy: { dataPublicacao: 'desc' },
        skip,
        take: params.pageSize,
      }),
      prisma.licitacao.count({ where }),
    ]);
  }

  const totalPages = Math.ceil(total / params.pageSize);
  const result = {
    data,
    pagination: {
      page: params.page,
      pageSize: params.pageSize,
      total,
      totalPages,
    },
  };

  await cache.set(cacheKey, result, 900);
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /stats - Aggregate statistics
// ---------------------------------------------------------------------------

router.get('/stats', asyncHandler(async (_req, res) => {
  const cacheKey = 'licitacoes:stats';

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const [
    totalCount,
    byEsfera,
    byModalidade,
    byStatus,
    newToday,
    avgValue,
  ] = await Promise.all([
    prisma.licitacao.count(),
    prisma.licitacao.groupBy({
      by: ['esfera'],
      _count: { id: true },
    }),
    prisma.licitacao.groupBy({
      by: ['modalidade'],
      _count: { id: true },
    }),
    prisma.licitacao.groupBy({
      by: ['status'],
      _count: { id: true },
    }),
    prisma.licitacao.count({
      where: { criadoEm: { gte: today } },
    }),
    prisma.licitacao.aggregate({
      _avg: { valorEstimado: true },
    }),
  ]);

  const result = {
    total: totalCount,
    novasHoje: newToday,
    valorMedio: avgValue._avg.valorEstimado,
    porEsfera: byEsfera.map((e) => ({ esfera: e.esfera, count: e._count.id })),
    porModalidade: byModalidade.map((m) => ({ modalidade: m.modalidade, count: m._count.id })),
    porStatus: byStatus.map((s) => ({ status: s.status, count: s._count.id })),
  };

  await cache.set(cacheKey, result, 900);
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /timeline - Upcoming licitacoes (next 30 days)
// ---------------------------------------------------------------------------

router.get('/timeline', asyncHandler(async (req, res) => {
  const params = timelineQuerySchema.parse(req.query);

  const now = new Date();
  const thirtyDaysFromNow = new Date();
  thirtyDaysFromNow.setDate(thirtyDaysFromNow.getDate() + 30);

  const where: Prisma.LicitacaoWhereInput = {
    dataAbertura: {
      gte: now,
      lte: thirtyDaysFromNow,
    },
  };

  if (params.esfera) where.esfera = params.esfera;
  if (params.uf) where.uf = params.uf.toUpperCase();
  if (params.modalidade) where.modalidade = params.modalidade;

  const data = await prisma.licitacao.findMany({
    where,
    orderBy: { dataAbertura: 'asc' },
    take: params.limit,
    select: {
      id: true,
      numeroEdital: true,
      modalidade: true,
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
  });

  res.json(data);
}));

// ---------------------------------------------------------------------------
// GET /:id - Single licitacao with all relations
// ---------------------------------------------------------------------------

router.get('/:id', asyncHandler(async (req, res) => {
  const id = req.params.id as string;
  const cacheKey = `licitacoes:detail:${id}`;

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const licitacao = await prisma.licitacao.findUnique({
    where: { id },
    include: {
      itens: {
        orderBy: { numero: 'asc' },
      },
      documentos: {
        orderBy: { criadoEm: 'desc' },
      },
      historico: {
        orderBy: { dataAlteracao: 'desc' },
      },
    },
  });

  if (!licitacao) {
    throw new AppError(404, 'Licitação não encontrada');
  }

  await cache.set(cacheKey, licitacao, 300); // 5 minutes
  res.json(licitacao);
}));

export { router as licitacoesRouter };
