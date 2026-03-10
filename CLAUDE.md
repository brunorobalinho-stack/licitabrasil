# CLAUDE.md - LicitaBrasil

## Project Overview

LicitaBrasil is a full-stack TypeScript monorepo that aggregates and searches Brazilian public procurement processes (licitações públicas). It scrapes data from federal (PNCP) and municipal (Querido Diário) sources, normalizes it, and provides a searchable interface with alerts, favorites, and dashboards.

## Architecture

```
licitabrasil/
├── backend/          # Express.js REST API + Prisma ORM + BullMQ workers
├── frontend/         # React 18 SPA with Vite + Tailwind CSS v4
└── docker-compose.yml  # PostgreSQL 16, Redis 7, backend, worker, frontend
```

**Backend**: Express.js on Node 20, TypeScript (ES2022, NodeNext modules), Prisma ORM with PostgreSQL, Redis caching via IORedis, BullMQ job queue, Pino logging.

**Frontend**: React 18, Vite 6, Tailwind CSS v4, Zustand state management, React Router 7, Radix UI components, Recharts for charts.

## Essential Commands

```bash
# Development (from root)
npm run dev                  # Runs backend + frontend concurrently
npm run dev:backend          # Backend only (tsx watch, port 3001)
npm run dev:frontend         # Frontend only (Vite, port 5173)

# Database
npm run db:migrate           # Run Prisma migrations
npm run db:seed              # Seed demo data (demo@licitabrasil.com.br / 123456)
npm run db:studio            # Open Prisma Studio

# Testing
npm test                     # Runs backend tests (Vitest)
cd backend && npx vitest run # Same, explicit

# Building
npm run build                # Build backend (tsc) + frontend (vite build)

# Background worker
npm run worker               # Start BullMQ worker + cron scheduler

# Linting
cd backend && npm run lint   # ESLint on backend src/

# Docker
npm run docker:up            # Start all services
npm run docker:down          # Stop all services
npm run docker:build         # Rebuild containers
```

## Code Structure

### Backend (`backend/src/`)

| Directory | Purpose |
|-----------|---------|
| `api/routes/` | Express route handlers: `auth`, `licitacoes`, `alertas`, `favoritos`, `buscas-salvas`, `dashboard`, `fontes` |
| `api/middleware/` | `auth.ts` (JWT verification), `error-handler.ts` (global error handler) |
| `config/env.ts` | Environment variable validation with Zod |
| `lib/` | Singletons: `prisma.ts`, `redis.ts` (cache helpers), `logger.ts` (Pino) |
| `scrapers/` | Template Method pattern: `base-scraper.ts` → `federal/pncp-scraper.ts`, `municipal/querido-diario.ts` |
| `jobs/` | `queues.ts` (BullMQ definitions), `worker.ts` (job processing), `scheduler.ts` (cron: PNCP every 30m, QD every 6h) |
| `server.ts` | Express app setup, middleware chain, route mounting |

### Frontend (`frontend/src/`)

| Directory | Purpose |
|-----------|---------|
| `pages/` | Route pages: `SearchPage`, `LoginPage`, `RegisterPage`, `DashboardPage`, `LicitacaoDetailPage` |
| `components/` | `search/` (FilterPanel, SearchBar, LicitacaoCard, ResultsList), `layout/` (Header) |
| `stores/` | Zustand stores: `auth-store.ts`, `search-store.ts` |
| `services/api.ts` | Axios HTTP client with automatic token refresh on 401 |
| `types/index.ts` | Shared TypeScript types and label maps |
| `lib/utils.ts` | Formatting helpers |

### Database (`backend/prisma/`)

- **ORM**: Prisma 6.3 with PostgreSQL 16
- **Schema**: `schema.prisma` — Core models: `Licitacao`, `ItemLicitacao`, `Documento`, `HistoricoStatus`, `Usuario`, `Alerta`, `AlertaMatch`, `Favorito`, `BuscaSalva`, `FonteDados`
- **Search**: PostgreSQL full-text search with `tsvector` (Portuguese), `pg_trgm` extension, GIN indexes
- **Enums**: `Modalidade` (14 types), `StatusLicitacao` (12 states), `Esfera`, `TipoLicitacao`, `FrequenciaAlerta`
- **Deduplication**: `hashConteudo` unique field on `Licitacao`

## API Routes

All routes are prefixed with `/api`. Public routes require no auth; protected routes require `Authorization: Bearer <token>`.

- `POST /api/auth/register`, `POST /api/auth/login`, `POST /api/auth/refresh`, `GET /api/auth/me`
- `GET /api/licitacoes` (paginated, filtered), `GET /api/licitacoes/search` (full-text), `GET /api/licitacoes/:id`, `GET /api/licitacoes/stats`, `GET /api/licitacoes/timeline`
- `GET /api/dashboard/resumo`, `GET /api/dashboard/por-estado`, `GET /api/dashboard/por-modalidade`, `GET /api/dashboard/tendencias`
- `CRUD /api/alertas`, `CRUD /api/favoritos`, `CRUD /api/buscas-salvas` (all require auth)
- `GET /api/fontes/status`, `GET /api/fontes/cobertura`
- `GET /api/health`

## Authentication

- JWT access token (15m) + refresh token (7d), bcrypt password hashing (10 rounds)
- Middleware: `authMiddleware` (required), `optionalAuth` (optional)
- Frontend stores tokens in localStorage, auto-refreshes on 401

## Testing

- **Framework**: Vitest with globals enabled, 15s timeout
- **Location**: `backend/tests/unit/` — tests for scrapers, auth, and licitacoes routes
- **Mocking**: Tests mock Prisma, Redis, and fetch (no real DB needed)
- **Run**: `npm test` from root or `npx vitest run` from `backend/`

## Key Conventions

- **Language**: All code is TypeScript with strict mode. All user-facing strings and data are in Portuguese.
- **Path aliases**: Backend uses `@/*` → `src/*` (configured in tsconfig)
- **Naming**: camelCase for variables/functions, PascalCase for types/classes/React components
- **API responses**: JSON with pagination (`page`, `pageSize` 1-100), cache TTL via Redis (15m search, 5m detail)
- **Error handling**: Centralized error handler middleware; routes use try/catch with appropriate HTTP status codes
- **Logging**: Pino structured logging throughout backend
- **Security**: Helmet headers, CORS, express-rate-limit, input validation with Zod
- **Scraper pattern**: Template Method — extend `BaseScraper`, implement `fetchData()` and `parseData()`. Base handles normalization, hashing, and deduplication.

## Environment Variables

Backend validates all env vars via Zod at startup (`backend/src/config/env.ts`). Key variables:

- `DATABASE_URL` — PostgreSQL connection string
- `REDIS_URL` — Redis connection string
- `JWT_SECRET`, `JWT_REFRESH_SECRET` — Token signing keys
- `PORT` (default 3001), `NODE_ENV`, `CORS_ORIGIN`
- `PNCP_API_BASE`, `QUERIDO_DIARIO_API_BASE` — Scraper API endpoints
- `SCRAPING_CONCURRENCY`, `SCRAPING_RATE_LIMIT_MS` — Scraper tuning

See `.env.example` for full reference.

## Docker Setup

`docker-compose.yml` defines 5 services: `postgres` (16-alpine), `redis` (7-alpine), `backend` (Express API on 3001), `worker` (BullMQ + cron), `frontend` (Nginx on 5173). Services have health checks and proper dependency ordering.
