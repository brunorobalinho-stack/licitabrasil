import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { Prisma } from '@prisma/client';
import crypto from 'crypto';
import { prisma } from '../../lib/prisma.js';
import { cache } from '../../lib/redis.js';
import { logger } from '../../lib/logger.js';
import { AppError } from '../middleware/error-handler.js';
import { sanitizeSearchQuery } from '../../lib/search-query.js';

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
  codigoUASG: z.string().optional(),
  ordenarPor: z.enum(['dataPublicacao', 'dataAbertura', 'valorEstimado', 'relevancia']).default('dataPublicacao'),
  ordem: z.enum(['asc', 'desc']).default('desc'),
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
  if (params.codigoUASG) {
    where.codigoUASG = params.codigoUASG;
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
// Shared select clause for list queries
// ---------------------------------------------------------------------------

const listSelect = {
  id: true,
  numeroEdital: true,
  numeroProcesso: true,
  codigoPNCP: true,
  codigoUASG: true,
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
} as const;

const listColumns = [
  'id', '"numeroEdital"', '"numeroProcesso"', '"codigoPNCP"', '"codigoUASG"',
  'modalidade', 'tipo', 'orgao', '"orgaoSigla"', 'esfera', 'uf', 'municipio',
  'objeto', '"objetoResumido"', '"valorEstimado"',
  '"dataPublicacao"', '"dataAbertura"', 'status', 'segmento',
  '"fonteOrigem"', '"urlOrigem"', '"criadoEm"',
].join(', ');

// ---------------------------------------------------------------------------
// Full-text search helper
// ---------------------------------------------------------------------------

async function fullTextSearch(
  tsQuery: string,
  params: z.infer<typeof listQuerySchema>,
): Promise<{
  data: Record<string, unknown>[];
  pagination: { page: number; pageSize: number; total: number; totalPages: number };
  highlights: Record<string, string>;
}> {
  const skip = (params.page - 1) * params.pageSize;
  const queryParams: unknown[] = [tsQuery];
  const conditions: string[] = [
    `"searchVector" @@ to_tsquery('portuguese', $1)`,
  ];

  let paramIndex = 2;

  if (params.esfera) {
    conditions.push(`esfera = $${paramIndex}::"Esfera"`);
    queryParams.push(params.esfera);
    paramIndex++;
  }
  if (params.uf) {
    conditions.push(`uf = $${paramIndex}`);
    queryParams.push(params.uf.toUpperCase());
    paramIndex++;
  }
  if (params.municipio) {
    conditions.push(`municipio ILIKE $${paramIndex}`);
    queryParams.push(`%${params.municipio}%`);
    paramIndex++;
  }
  if (params.modalidade) {
    conditions.push(`modalidade = $${paramIndex}::"Modalidade"`);
    queryParams.push(params.modalidade);
    paramIndex++;
  }
  if (params.tipo) {
    conditions.push(`tipo = $${paramIndex}::"TipoLicitacao"`);
    queryParams.push(params.tipo);
    paramIndex++;
  }
  if (params.status) {
    conditions.push(`status = $${paramIndex}::"StatusLicitacao"`);
    queryParams.push(params.status);
    paramIndex++;
  }
  if (params.segmento) {
    conditions.push(`segmento ILIKE $${paramIndex}`);
    queryParams.push(`%${params.segmento}%`);
    paramIndex++;
  }
  if (params.orgao) {
    conditions.push(`orgao ILIKE $${paramIndex}`);
    queryParams.push(`%${params.orgao}%`);
    paramIndex++;
  }
  if (params.valorMin !== undefined) {
    conditions.push(`"valorEstimado" >= $${paramIndex}`);
    queryParams.push(params.valorMin);
    paramIndex++;
  }
  if (params.valorMax !== undefined) {
    conditions.push(`"valorEstimado" <= $${paramIndex}`);
    queryParams.push(params.valorMax);
    paramIndex++;
  }
  if (params.dataPublicacaoInicio) {
    conditions.push(`"dataPublicacao" >= $${paramIndex}`);
    queryParams.push(new Date(params.dataPublicacaoInicio));
    paramIndex++;
  }
  if (params.dataPublicacaoFim) {
    conditions.push(`"dataPublicacao" <= $${paramIndex}`);
    queryParams.push(new Date(params.dataPublicacaoFim));
    paramIndex++;
  }
  if (params.dataAberturaInicio) {
    conditions.push(`"dataAbertura" >= $${paramIndex}`);
    queryParams.push(new Date(params.dataAberturaInicio));
    paramIndex++;
  }
  if (params.dataAberturaFim) {
    conditions.push(`"dataAbertura" <= $${paramIndex}`);
    queryParams.push(new Date(params.dataAberturaFim));
    paramIndex++;
  }
  if (params.fonteOrigem) {
    conditions.push(`"fonteOrigem" = $${paramIndex}`);
    queryParams.push(params.fonteOrigem);
    paramIndex++;
  }
  if (params.codigoUASG) {
    conditions.push(`"codigoUASG" = $${paramIndex}`);
    queryParams.push(params.codigoUASG);
    paramIndex++;
  }

  const whereSQL = conditions.join(' AND ');

  // Count query
  const countSQL = `SELECT COUNT(*) as count FROM "Licitacao" WHERE ${whereSQL}`;
  const countResult = await prisma.$queryRawUnsafe<[{ count: bigint }]>(
    countSQL,
    ...queryParams,
  );
  const total = Number(countResult[0].count);

  // Ordering — whitelist estrito (defense in depth, mesmo com Zod enum)
  const SAFE_COLUMNS: Record<string, string> = {
    relevancia: `ts_rank("searchVector", to_tsquery('portuguese', $1))`,
    dataAbertura: '"dataAbertura"',
    valorEstimado: '"valorEstimado"',
    dataPublicacao: '"dataPublicacao"',
  };
  const direction = params.ordem === 'asc' ? 'ASC' : 'DESC';
  const column = SAFE_COLUMNS[params.ordenarPor] ?? SAFE_COLUMNS.dataPublicacao;
  const orderClause = `${column} ${direction}`;

  // Data query with headline and rank
  const limitIdx = paramIndex;
  const offsetIdx = paramIndex + 1;
  queryParams.push(params.pageSize, skip);

  const dataSQL = `SELECT ${listColumns},
    ts_rank("searchVector", to_tsquery('portuguese', $1)) AS rank,
    ts_headline('portuguese', objeto, to_tsquery('portuguese', $1), 'StartSel=<mark>, StopSel=</mark>, MaxFragments=2, MaxWords=30') AS headline
    FROM "Licitacao"
    WHERE ${whereSQL}
    ORDER BY ${orderClause}
    LIMIT $${limitIdx} OFFSET $${offsetIdx}`;

  const rows = await prisma.$queryRawUnsafe<
    (Record<string, unknown> & { rank: number; headline: string })[]
  >(dataSQL, ...queryParams);

  // Build highlights map and strip rank/headline from data
  const highlights: Record<string, string> = {};
  const data = rows.map(({ rank: _rank, headline, ...row }) => {
    if (headline) {
      highlights[row.id as string] = headline;
    }
    return row;
  });

  const totalPages = Math.ceil(total / params.pageSize);

  return {
    data,
    pagination: { page: params.page, pageSize: params.pageSize, total, totalPages },
    highlights,
  };
}

// ---------------------------------------------------------------------------
// GET / - List licitacoes with filters
// ---------------------------------------------------------------------------
/** @openapi
 * /licitacoes:
 *   get:
 *     tags: [Licitações]
 *     summary: Listar licitações com filtros e full-text search
 *     parameters:
 *       - in: query
 *         name: q
 *         schema: { type: string }
 *         description: Busca textual (full-text + ILIKE fallback)
 *       - in: query
 *         name: page
 *         schema: { type: integer, default: 1 }
 *       - in: query
 *         name: pageSize
 *         schema: { type: integer, default: 20, maximum: 100 }
 *       - in: query
 *         name: esfera
 *         schema: { type: string, enum: [FEDERAL, ESTADUAL, MUNICIPAL] }
 *       - in: query
 *         name: uf
 *         schema: { type: string }
 *       - in: query
 *         name: modalidade
 *         schema: { type: string }
 *       - in: query
 *         name: status
 *         schema: { type: string }
 *       - in: query
 *         name: valorMin
 *         schema: { type: number }
 *       - in: query
 *         name: valorMax
 *         schema: { type: number }
 *       - in: query
 *         name: ordenarPor
 *         schema: { type: string, enum: [dataPublicacao, dataAbertura, valorEstimado, relevancia], default: dataPublicacao }
 *       - in: query
 *         name: ordem
 *         schema: { type: string, enum: [asc, desc], default: desc }
 *     responses:
 *       200:
 *         description: Lista paginada de licitações
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/PaginatedLicitacoes'
 */
router.get('/', asyncHandler(async (req, res) => {
  const params = listQuerySchema.parse(req.query);
  const cacheKey = `licitacoes:list:${hashQuery(params)}`;

  const cached = await cache.get<unknown>(cacheKey);
  if (cached) {
    res.json(cached);
    return;
  }

  const tsQuery = params.q ? sanitizeSearchQuery(params.q) : null;

  // When a search query is present, attempt full-text search via tsvector
  if (tsQuery) {
    try {
      const result = await fullTextSearch(tsQuery, params);
      await cache.set(cacheKey, result, 900);
      res.json(result);
      return;
    } catch (err) {
      logger.warn({ err }, 'Full-text search fallback to ILIKE on GET /');
      // Fall through to standard Prisma query below
    }
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
      select: listSelect,
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
    highlights: {} as Record<string, string>,
  };

  await cache.set(cacheKey, result, 900); // 15 minutes
  res.json(result);
}));

// ---------------------------------------------------------------------------
// GET /stats - Aggregate statistics
// ---------------------------------------------------------------------------
/** @openapi
 * /licitacoes/stats:
 *   get:
 *     tags: [Licitações]
 *     summary: Estatísticas agregadas (total, por esfera, modalidade, status)
 *     responses:
 *       200:
 *         description: Estatísticas
 */
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
/** @openapi
 * /licitacoes/timeline:
 *   get:
 *     tags: [Licitações]
 *     summary: Licitações com abertura nos próximos 30 dias
 *     parameters:
 *       - in: query
 *         name: esfera
 *         schema: { type: string }
 *       - in: query
 *         name: uf
 *         schema: { type: string }
 *       - in: query
 *         name: modalidade
 *         schema: { type: string }
 *       - in: query
 *         name: limit
 *         schema: { type: integer, default: 50, maximum: 200 }
 *     responses:
 *       200:
 *         description: Array de licitações
 */
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
/** @openapi
 * /licitacoes/{id}:
 *   get:
 *     tags: [Licitações]
 *     summary: Detalhes de uma licitação (inclui itens, documentos, histórico)
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema: { type: string }
 *     responses:
 *       200:
 *         description: Licitação com relações
 *       404:
 *         description: Não encontrada
 */
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
