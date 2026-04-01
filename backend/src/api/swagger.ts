import swaggerJsdoc from 'swagger-jsdoc';
import swaggerUi from 'swagger-ui-express';
import { Express } from 'express';

const options: swaggerJsdoc.Options = {
  definition: {
    openapi: '3.0.3',
    info: {
      title: 'LicitaBrasil API',
      version: '1.0.0',
      description: 'API para agregação e monitoramento de licitações públicas brasileiras.',
    },
    servers: [
      { url: '/api/v1', description: 'API v1' },
    ],
    components: {
      securitySchemes: {
        cookieAuth: {
          type: 'apiKey',
          in: 'cookie',
          name: 'accessToken',
        },
      },
      schemas: {
        // ── Auth ──────────────────────────────────────
        LoginRequest: {
          type: 'object',
          required: ['email', 'senha'],
          properties: {
            email: { type: 'string', format: 'email' },
            senha: { type: 'string', minLength: 1 },
          },
        },
        RegisterRequest: {
          type: 'object',
          required: ['email', 'nome', 'senha'],
          properties: {
            email: { type: 'string', format: 'email' },
            nome: { type: 'string', minLength: 2 },
            senha: { type: 'string', minLength: 6 },
            empresa: { type: 'string' },
            cnpj: { type: 'string' },
          },
        },
        Usuario: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            email: { type: 'string' },
            nome: { type: 'string' },
            empresa: { type: 'string', nullable: true },
            cnpj: { type: 'string', nullable: true },
            role: { type: 'string', enum: ['ADMIN', 'ANALYST', 'USER'] },
            criadoEm: { type: 'string', format: 'date-time' },
            atualizadoEm: { type: 'string', format: 'date-time' },
          },
        },
        // ── Licitação ─────────────────────────────────
        Licitacao: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            numeroEdital: { type: 'string', nullable: true },
            numeroProcesso: { type: 'string', nullable: true },
            modalidade: { type: 'string', enum: ['PREGAO_ELETRONICO', 'PREGAO_PRESENCIAL', 'CONCORRENCIA', 'CONCORRENCIA_ELETRONICA', 'TOMADA_DE_PRECOS', 'CONVITE', 'CONCURSO', 'LEILAO', 'DIALOGO_COMPETITIVO', 'DISPENSA', 'INEXIGIBILIDADE', 'CREDENCIAMENTO', 'RDC', 'OUTRA'] },
            tipo: { type: 'string', enum: ['COMPRA', 'SERVICO', 'OBRA', 'SERVICO_ENGENHARIA', 'ALIENACAO', 'CONCESSAO', 'PERMISSAO', 'LOCACAO', 'OUTRO'] },
            orgao: { type: 'string' },
            esfera: { type: 'string', enum: ['FEDERAL', 'ESTADUAL', 'MUNICIPAL'] },
            uf: { type: 'string', nullable: true },
            municipio: { type: 'string', nullable: true },
            objeto: { type: 'string' },
            objetoResumido: { type: 'string', nullable: true },
            valorEstimado: { type: 'number', nullable: true },
            status: { type: 'string', enum: ['PUBLICADA', 'ABERTA', 'EM_ANDAMENTO', 'SUSPENSA', 'ADIADA', 'ENCERRADA', 'ANULADA', 'REVOGADA', 'DESERTA', 'FRACASSADA', 'HOMOLOGADA', 'ADJUDICADA'] },
            dataPublicacao: { type: 'string', format: 'date-time' },
            dataAbertura: { type: 'string', format: 'date-time', nullable: true },
            fonteOrigem: { type: 'string' },
            urlOrigem: { type: 'string' },
            criadoEm: { type: 'string', format: 'date-time' },
          },
        },
        PaginatedLicitacoes: {
          type: 'object',
          properties: {
            data: { type: 'array', items: { $ref: '#/components/schemas/Licitacao' } },
            pagination: { $ref: '#/components/schemas/Pagination' },
            highlights: { type: 'object', additionalProperties: { type: 'string' } },
          },
        },
        Pagination: {
          type: 'object',
          properties: {
            page: { type: 'integer' },
            pageSize: { type: 'integer' },
            total: { type: 'integer' },
            totalPages: { type: 'integer' },
          },
        },
        // ── Alerta ────────────────────────────────────
        Alerta: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            palavrasChave: { type: 'array', items: { type: 'string' } },
            modalidades: { type: 'array', items: { type: 'string' } },
            esferas: { type: 'array', items: { type: 'string' } },
            estados: { type: 'array', items: { type: 'string' } },
            frequencia: { type: 'string', enum: ['TEMPO_REAL', 'DIARIO', 'SEMANAL'] },
            ativo: { type: 'boolean' },
            totalEnviados: { type: 'integer' },
            criadoEm: { type: 'string', format: 'date-time' },
          },
        },
        CreateAlertaRequest: {
          type: 'object',
          required: ['palavrasChave', 'frequencia', 'canalNotificacao'],
          properties: {
            palavrasChave: { type: 'array', items: { type: 'string' }, minItems: 1 },
            modalidades: { type: 'array', items: { type: 'string' } },
            esferas: { type: 'array', items: { type: 'string' } },
            estados: { type: 'array', items: { type: 'string' } },
            municipios: { type: 'array', items: { type: 'string' } },
            segmentos: { type: 'array', items: { type: 'string' } },
            valorMinimo: { type: 'number' },
            valorMaximo: { type: 'number' },
            frequencia: { type: 'string', enum: ['TEMPO_REAL', 'DIARIO', 'SEMANAL'] },
            canalNotificacao: { type: 'array', items: { type: 'string' }, minItems: 1 },
          },
        },
        // ── Favorito ──────────────────────────────────
        Favorito: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            licitacaoId: { type: 'string' },
            notas: { type: 'string', nullable: true },
            tags: { type: 'array', items: { type: 'string' } },
            licitacao: { $ref: '#/components/schemas/Licitacao' },
            criadoEm: { type: 'string', format: 'date-time' },
          },
        },
        // ── Busca Salva ───────────────────────────────
        BuscaSalva: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            nome: { type: 'string' },
            filtros: { type: 'object' },
            criadoEm: { type: 'string', format: 'date-time' },
          },
        },
        // ── Dashboard ─────────────────────────────────
        DashboardResumo: {
          type: 'object',
          properties: {
            novasHoje: { type: 'integer' },
            abertasEstaSemana: { type: 'integer' },
            encerradasEstaSemana: { type: 'integer' },
            volumeTotalAbertas: { type: 'number', nullable: true },
          },
        },
        // ── Fonte ─────────────────────────────────────
        FonteDados: {
          type: 'object',
          properties: {
            id: { type: 'string' },
            nome: { type: 'string' },
            url: { type: 'string' },
            tipo: { type: 'string' },
            esfera: { type: 'string' },
            ativo: { type: 'boolean' },
            healthy: { type: 'boolean' },
            totalColetados: { type: 'integer' },
            totalErros: { type: 'integer' },
            ultimoSucesso: { type: 'string', format: 'date-time', nullable: true },
          },
        },
        // ── Error ─────────────────────────────────────
        Error: {
          type: 'object',
          properties: {
            error: { type: 'string' },
          },
        },
      },
    },
  },
  apis: ['./src/api/routes/*.ts'],
};

const swaggerSpec = swaggerJsdoc(options);

export function setupSwagger(app: Express) {
  app.use('/api/docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec, {
    customSiteTitle: 'LicitaBrasil API Docs',
    customCss: '.swagger-ui .topbar { display: none }',
  }));

  app.get('/api/docs.json', (_req, res) => {
    res.json(swaggerSpec);
  });
}
