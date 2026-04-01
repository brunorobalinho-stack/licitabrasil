# LicitaBrasil

Agregador unificado de licitações públicas brasileiras. Consolida dados de portais federais (PNCP), estaduais e municipais (Querido Diário) em uma plataforma única de busca para empresários e fornecedores.

## Stack Tecnológica

| Camada     | Tecnologia                                                   |
|------------|--------------------------------------------------------------|
| Frontend   | React 18, TypeScript, Tailwind CSS v4, Zustand, Recharts     |
| Backend    | Express 4, TypeScript, Prisma ORM, Zod                       |
| Banco      | PostgreSQL 16 (tsvector full-text search, GIN indexes)       |
| Cache/Fila | Redis 7, BullMQ                                              |
| Scrapers   | Node.js (fetch + Cheerio), node-cron scheduler               |
| Infra      | Docker Compose (5 serviços)                                  |

## Funcionalidades (Fase 1 — MVP)

- **Busca unificada** com full-text search em português (tsvector + GIN)
- **18 filtros** — esfera, UF, modalidade, tipo, status, valor, datas, segmento, órgão, fonte
- **Dashboard** com KPIs, gráficos por estado/modalidade e tendência 30 dias
- **Alertas** personalizados por palavras-chave, filtros e frequência
- **Favoritos** com notas e tags
- **Buscas salvas** para reexecutar filtros
- **Scraping automatizado** — PNCP a cada 30 min, Querido Diário a cada 6h
- **Deduplicação** por hash SHA-256 (edital + órgão + objeto + data)
- **Autenticação JWT** com access + refresh tokens
- **Cache Redis** em endpoints pesados (15 min TTL)
- **Dark mode** no frontend

## Pré-requisitos

- [Node.js](https://nodejs.org/) 20+
- [Docker](https://www.docker.com/) e Docker Compose
- Git

## Início Rápido

### 1. Clonar e configurar

```bash
git clone <repo-url> licitabrasil
cd licitabrasil
cp .env.example .env
```

### 2. Subir com Docker Compose (recomendado)

```bash
docker compose up -d
```

Isso inicia 5 serviços:

| Serviço    | Porta  | Descrição                           |
|------------|--------|-------------------------------------|
| postgres   | 5432   | PostgreSQL 16 Alpine                |
| redis      | 6379   | Redis 7 Alpine                      |
| backend    | 3001   | API Express                         |
| worker     | —      | BullMQ worker + cron scheduler      |
| frontend   | 80     | React app via Nginx                 |

### 3. Desenvolvimento local (sem Docker)

```bash
# Terminal 1 — Backend
cd backend
npm install
npx prisma generate
npx prisma migrate deploy
npx prisma db seed
npm run dev

# Terminal 2 — Worker
cd backend
npm run worker

# Terminal 3 — Frontend
cd frontend
npm install
npm run dev
```

O frontend estará em `http://localhost:5173` com proxy automático para a API.

### 4. Usuário demo

Após seed:

| Campo | Valor                       |
|-------|-----------------------------|
| Email | demo@licitabrasil.com.br    |
| Senha | 123456                      |

## Estrutura do Projeto

```
licitabrasil/
├── backend/
│   ├── prisma/
│   │   ├── schema.prisma         # Modelos, enums, indexes
│   │   ├── seed.ts               # Dados demo
│   │   └── migrations/           # SQL migrations
│   ├── src/
│   │   ├── config/env.ts         # Variáveis com validação Zod
│   │   ├── lib/                  # Prisma, Redis, Logger
│   │   ├── api/
│   │   │   ├── middleware/       # Auth JWT, error handler
│   │   │   └── routes/           # auth, licitacoes, alertas, favoritos...
│   │   ├── scrapers/
│   │   │   ├── base-scraper.ts   # Template Method + normalização PT-BR
│   │   │   ├── federal/          # PNCP
│   │   │   └── municipal/        # Querido Diário
│   │   ├── jobs/
│   │   │   ├── queues.ts         # Definição filas BullMQ
│   │   │   ├── worker.ts         # Processador de jobs
│   │   │   └── scheduler.ts      # Cron (node-cron) → PNCP + QD (NÃO EXISTE AQUI, está em scrapers/)
│   │   └── server.ts             # Express app
│   └── tests/                    # Vitest unit tests
├── frontend/
│   ├── src/
│   │   ├── components/           # Header, SearchBar, FilterPanel, LicitacaoCard, ResultsList
│   │   ├── pages/                # SearchPage, DashboardPage, LicitacaoDetailPage, LoginPage
│   │   ├── stores/               # Zustand (auth, search)
│   │   ├── services/api.ts       # Cliente HTTP com auto-refresh
│   │   ├── types/index.ts        # Tipos + label maps PT-BR
│   │   └── lib/utils.ts          # cn(), formatCurrency(), formatDate()
│   └── nginx.conf                # SPA fallback + proxy reverso
├── docker-compose.yml
└── .env.example
```

## API Endpoints

### Auth
| Método | Rota                | Descrição            | Auth |
|--------|---------------------|----------------------|------|
| POST   | /api/auth/register  | Criar conta          | Não  |
| POST   | /api/auth/login     | Login                | Não  |
| POST   | /api/auth/refresh   | Renovar tokens       | Não  |
| GET    | /api/auth/me        | Perfil atual         | Sim  |

### Licitações
| Método | Rota                      | Descrição                     | Auth |
|--------|---------------------------|-------------------------------|------|
| GET    | /api/licitacoes           | Listar com filtros + paginação| Não  |
| GET    | /api/licitacoes/search    | Busca full-text               | Não  |
| GET    | /api/licitacoes/stats     | Estatísticas agregadas        | Não  |
| GET    | /api/licitacoes/timeline  | Próximas 30 dias              | Não  |
| GET    | /api/licitacoes/:id       | Detalhe com itens e documentos| Não  |

### Dashboard
| Método | Rota                          | Descrição                | Auth |
|--------|-------------------------------|--------------------------|------|
| GET    | /api/dashboard/resumo         | KPIs (hoje, semana)      | Não  |
| GET    | /api/dashboard/por-estado     | Contagem por UF          | Não  |
| GET    | /api/dashboard/por-modalidade | Contagem por modalidade  | Não  |
| GET    | /api/dashboard/tendencias     | Publicações por dia (30d)| Não  |

### Alertas (auth required)
| Método | Rota              | Descrição        |
|--------|--------------------|------------------|
| POST   | /api/alertas       | Criar alerta     |
| GET    | /api/alertas       | Listar alertas   |
| PUT    | /api/alertas/:id   | Atualizar alerta |
| DELETE | /api/alertas/:id   | Excluir alerta   |

### Favoritos (auth required)
| Método | Rota               | Descrição                  |
|--------|---------------------|---------------------------|
| POST   | /api/favoritos      | Adicionar favorito (upsert)|
| GET    | /api/favoritos      | Listar favoritos paginados |
| DELETE | /api/favoritos/:id  | Remover favorito           |

### Buscas Salvas (auth required)
| Método | Rota                   | Descrição            |
|--------|-------------------------|---------------------|
| POST   | /api/buscas-salvas      | Salvar busca        |
| GET    | /api/buscas-salvas      | Listar buscas salvas|
| DELETE | /api/buscas-salvas/:id  | Excluir busca salva |

### Fontes de Dados
| Método | Rota                 | Descrição                           |
|--------|----------------------|-------------------------------------|
| GET    | /api/fontes/status   | Status + saúde de cada fonte        |
| GET    | /api/fontes/cobertura| Cobertura por esfera e UF           |

## Testes

```bash
cd backend
npm test              # Executar testes
npm run test:watch    # Modo watch
```

Os testes usam Vitest com mocks para Prisma/Redis/fetch, sem necessidade de banco real.

## Variáveis de Ambiente

| Variável                  | Descrição                         | Default                          |
|---------------------------|-----------------------------------|----------------------------------|
| DATABASE_URL              | URL de conexão PostgreSQL         | —                                |
| REDIS_URL                 | URL de conexão Redis              | redis://localhost:6379           |
| JWT_SECRET                | Segredo para access tokens        | —                                |
| JWT_REFRESH_SECRET        | Segredo para refresh tokens       | —                                |
| JWT_EXPIRES_IN            | Expiração do access token         | 15m                              |
| JWT_REFRESH_EXPIRES_IN    | Expiração do refresh token        | 7d                               |
| PORT                      | Porta da API                      | 3001                             |
| NODE_ENV                  | Ambiente                          | development                      |
| CORS_ORIGIN               | Origem permitida para CORS        | http://localhost:5173            |
| PNCP_API_BASE             | URL base da API PNCP              | https://pncp.gov.br/api/consulta|
| QUERIDO_DIARIO_API_BASE   | URL base da API Querido Diário    | https://queridodiario.ok.org.br/api |
| SCRAPING_RATE_LIMIT_MS    | Rate limit entre requests (ms)    | 1000                             |

## Arquitetura de Scraping

```
┌─────────────┐     ┌──────────┐     ┌──────────┐
│  node-cron  │────▶│  BullMQ  │────▶│  Worker  │
│  Scheduler  │     │  Queue   │     │          │
└─────────────┘     └──────────┘     └────┬─────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
             ┌──────▼──────┐    ┌────────▼────────┐   ┌───────▼──────┐
             │ PNCPScraper │    │ QueridoDiário   │   │  Futuras...  │
             │ (API REST)  │    │ (API + regex)   │   │              │
             └──────┬──────┘    └────────┬────────┘   └──────────────┘
                    │                     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   BaseScraper       │
                    │  • normalizeEnum()  │
                    │  • generateHash()   │
                    │  • withRetry()      │
                    │  • rateLimit()      │
                    │  • saveToDatabase() │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  PostgreSQL         │
                    │  (upsert on hash)   │
                    └─────────────────────┘
```

### Fluxo de Deduplicação

1. Cada licitação gera um **hash SHA-256** de `edital + órgão + objeto + dataPublicação`
2. `BaseScraper.saveToDatabase()` faz `findUnique(hashConteudo)` e decide `create` vs `update`
3. O mesmo edital em fontes diferentes produz o mesmo hash → atualiza em vez de duplicar

## Roadmap (Próximas Fases)

- **Fase 2**: ComprasNet, BEC-SP, CELIC-RS, mapa interativo por UF
- **Fase 3**: OCR para documentos PDF, análise de tendências com ML
- **Fase 4**: PWA, notificações push, pesquisa por voz
- **Fase 5**: API pública com rate limiting e planos de assinatura

## Licença

Projeto privado. Todos os direitos reservados.
