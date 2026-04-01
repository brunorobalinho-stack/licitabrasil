# Auditor de Folha de Pagamento — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a standalone payroll audit system that extracts data from PDF payslips, applies 13 configurable audit rules, and displays results in a dashboard.

**Architecture:** Express + Prisma + PostgreSQL backend (port 3002) with React + Vite + Tailwind v4 frontend (port 5174). PDF extraction via Python `pdfplumber` called from Node.js via `child_process`. Audit engine with pure-function rules and configurable thresholds. No auth for MVP.

**Tech Stack:** Express 4, Prisma 6, PostgreSQL 16, React 19, Vite 6, Tailwind CSS v4, Zustand 5, Zod, multer, lucide-react, Radix UI, react-router-dom 7, Python 3 + pdfplumber (PDF extraction)

**Design doc:** `docs/plans/2026-03-02-auditor-folha-design.md` (in licitabrasil repo)

---

## Task 1: Project Scaffolding — Root + Backend Init

**Files:**
- Create: `C:/Users/bruno/auditor-folha/package.json`
- Create: `C:/Users/bruno/auditor-folha/backend/package.json`
- Create: `C:/Users/bruno/auditor-folha/backend/tsconfig.json`
- Create: `C:/Users/bruno/auditor-folha/backend/.env`
- Create: `C:/Users/bruno/auditor-folha/backend/scripts/extract_pdf.py`
- Create: `C:/Users/bruno/auditor-folha/backend/scripts/requirements.txt`
- Create: `C:/Users/bruno/auditor-folha/.gitignore`

**Step 1: Create root directory and root `package.json`**

```bash
mkdir -p C:/Users/bruno/auditor-folha
```

```json
// C:/Users/bruno/auditor-folha/package.json
{
  "name": "auditor-folha",
  "version": "1.0.0",
  "private": true,
  "description": "Sistema de Auditoria de Folhas de Pagamento",
  "scripts": {
    "dev": "concurrently \"npm run dev:backend\" \"npm run dev:frontend\"",
    "dev:backend": "cd backend && npm run dev",
    "dev:frontend": "cd frontend && npm run dev",
    "build": "npm run build:backend && npm run build:frontend",
    "build:backend": "cd backend && npm run build",
    "build:frontend": "cd frontend && npm run build",
    "db:migrate": "cd backend && npx prisma migrate dev",
    "db:seed": "cd backend && npx prisma db seed",
    "db:studio": "cd backend && npx prisma studio",
    "test": "cd backend && npm test"
  },
  "devDependencies": {
    "concurrently": "^9.1.0"
  }
}
```

**Step 2: Create backend `package.json`**

```json
// C:/Users/bruno/auditor-folha/backend/package.json
{
  "name": "auditor-folha-backend",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/server.ts",
    "build": "tsc",
    "start": "node dist/server.js",
    "test": "vitest run",
    "test:watch": "vitest",
    "prisma:generate": "prisma generate",
    "prisma:migrate": "prisma migrate dev",
    "prisma:seed": "tsx prisma/seed.ts"
  },
  "dependencies": {
    "@prisma/client": "^6.3.0",
    "compression": "^1.7.4",
    "cors": "^2.8.5",
    "dotenv": "^16.4.7",
    "express": "^4.21.1",
    "helmet": "^8.0.0",
    "multer": "^1.4.5-lts.1",
    "pino": "^9.5.0",
    "pino-http": "^10.3.0",
    "pino-pretty": "^13.0.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@types/compression": "^1.7.5",
    "@types/cors": "^2.8.17",
    "@types/express": "^5.0.0",
    "@types/multer": "^1.4.12",
    "@types/node": "^22.10.0",
    "@types/supertest": "^6.0.2",
    "prisma": "^6.3.0",
    "supertest": "^7.0.0",
    "tsx": "^4.19.2",
    "typescript": "^5.7.2",
    "vitest": "^2.1.8"
  }
}
```

**Step 3: Create backend `tsconfig.json`**

```json
// C:/Users/bruno/auditor-folha/backend/tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "NodeNext",
    "moduleResolution": "NodeNext",
    "lib": ["ES2022"],
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "resolveJsonModule": true,
    "declaration": true,
    "sourceMap": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src/**/*"],
  "exclude": ["node_modules", "dist", "tests"]
}
```

**Step 4: Create `.env`**

```env
# C:/Users/bruno/auditor-folha/backend/.env
DATABASE_URL="postgresql://postgres:postgres@localhost:5432/auditor_folha?schema=public"
PORT=3002
NODE_ENV=development
CORS_ORIGIN=http://localhost:5174
LOG_LEVEL=debug
```

**Step 5: Create `.gitignore`**

```gitignore
# C:/Users/bruno/auditor-folha/.gitignore
node_modules/
dist/
.env
*.log
backend/uploads/
backend/scripts/__pycache__/
backend/scripts/.venv/
```

**Step 6: Create Python PDF extraction script**

```txt
# C:/Users/bruno/auditor-folha/backend/scripts/requirements.txt
pdfplumber==0.11.4
```

Create `C:/Users/bruno/auditor-folha/backend/scripts/extract_pdf.py`:

A Python script that uses pdfplumber to extract employee payroll data from PDFs.
- Input: PDF file path as `sys.argv[1]`
- Output: JSON array of employee objects to stdout
- Uses `pdfplumber.open()` to extract tables, falls back to text parsing with regex
- Maps Brazilian rubrica names to standardized field names
- Handles Brazilian decimal format (`1.412,00` -> `1412.00`)
- CPF cleaning (remove dots/dashes)
- Unknown rubricas go to `outrosProventos`/`outrosDescontos` + `observacoes` list
- Error output as JSON `{"error": "message"}` to stdout with exit code 1

The full script includes:
1. `parse_br_decimal(value)` — Brazilian number format converter
2. `clean_cpf(cpf)` — Strip non-digits from CPF
3. `extract_from_pdf(pdf_path)` — Main extraction using pdfplumber tables
4. `parse_text_fallback(text)` — Line-by-line regex fallback
5. Rubrica mapping dictionary (same patterns as rubrica-mapper.ts)
6. `__main__` block that reads argv[1] and prints JSON

**IMPORTANT:** This parser must be calibrated with real PDFs from the user. The regex patterns are starter patterns.

**Step 7: Install Python dependencies**

```bash
cd C:/Users/bruno/auditor-folha/backend/scripts
pip install -r requirements.txt
```

**Step 8: Install Node.js dependencies**

```bash
cd C:/Users/bruno/auditor-folha && npm install
cd backend && npm install
```

**Step 9: Create PostgreSQL database**

```bash
C:/Users/bruno/.postgres/pgsql/bin/createdb -U postgres auditor_folha
```

**Step 10: Init git repo and commit**

```bash
cd C:/Users/bruno/auditor-folha
git init
git add -A
git commit -m "chore: scaffold project structure"
```

---

## Task 2: Prisma Schema + Migration

**Files:**
- Create: `C:/Users/bruno/auditor-folha/backend/prisma/schema.prisma`

**Step 1: Write the Prisma schema**

```prisma
// C:/Users/bruno/auditor-folha/backend/prisma/schema.prisma

generator client {
  provider   = "prisma-client-js"
  engineType = "binary"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

// =========================================================
// Enums
// =========================================================

enum StatusProcessamento {
  PENDENTE
  PROCESSANDO
  CONCLUIDO
  ERRO
}

enum Gravidade {
  CRITICO
  ALERTA
  OPORTUNIDADE
}

// =========================================================
// Models
// =========================================================

model ConvencaoColetiva {
  id             String    @id @default(cuid())
  nome           String
  sindicato      String
  vigenciaInicio DateTime
  vigenciaFim    DateTime
  createdAt      DateTime  @default(now())
  pisos          PisoCCT[]
  contratos      Contrato[]
}

model PisoCCT {
  id                      String             @id @default(cuid())
  cctId                   String
  cct                     ConvencaoColetiva  @relation(fields: [cctId], references: [id], onDelete: Cascade)
  cargo                   String
  pisoSalarial            Decimal            @db.Decimal(12, 2)
  adicionalInsalubridade  Decimal?           @db.Decimal(12, 2)
  adicionalPericulosidade Decimal?           @db.Decimal(12, 2)
  adicionalNoturno        Decimal?           @db.Decimal(12, 2)

  @@unique([cctId, cargo])
}

model Contrato {
  id        String             @id @default(cuid())
  codigo    String             @unique
  nome      String
  cctId     String?
  cct       ConvencaoColetiva? @relation(fields: [cctId], references: [id])
  createdAt DateTime           @default(now())
  folhas    FolhaPagamento[]
}

model FolhaPagamento {
  id             String              @id @default(cuid())
  contratoId     String
  contrato       Contrato            @relation(fields: [contratoId], references: [id], onDelete: Cascade)
  mesReferencia  String
  arquivoPdf     String
  status         StatusProcessamento @default(PENDENTE)
  totalProventos Decimal?            @db.Decimal(12, 2)
  totalDescontos Decimal?            @db.Decimal(12, 2)
  totalLiquido   Decimal?            @db.Decimal(12, 2)
  erroMsg        String?
  processadoEm   DateTime?
  createdAt      DateTime            @default(now())
  funcionarios   FuncionarioFolha[]
  flags          AuditFlag[]

  @@unique([contratoId, mesReferencia])
}

model FuncionarioFolha {
  id                      String         @id @default(cuid())
  folhaId                 String
  folha                   FolhaPagamento @relation(fields: [folhaId], references: [id], onDelete: Cascade)
  nome                    String
  cpf                     String
  cargo                   String
  salarioBase             Decimal        @db.Decimal(12, 2)
  horasNormais            Decimal        @default(0) @db.Decimal(12, 2)
  horasExtras50           Decimal        @default(0) @db.Decimal(12, 2)
  horasExtras100          Decimal        @default(0) @db.Decimal(12, 2)
  adicionalNoturno        Decimal        @default(0) @db.Decimal(12, 2)
  adicionalInsalubridade  Decimal        @default(0) @db.Decimal(12, 2)
  adicionalPericulosidade Decimal        @default(0) @db.Decimal(12, 2)
  faltasDias              Int            @default(0)
  faltasDesconto          Decimal        @default(0) @db.Decimal(12, 2)
  atestadosDias           Int            @default(0)
  dsrDesconto             Decimal        @default(0) @db.Decimal(12, 2)
  valeTransporte          Decimal        @default(0) @db.Decimal(12, 2)
  valeAlimentacao         Decimal        @default(0) @db.Decimal(12, 2)
  inss                    Decimal        @default(0) @db.Decimal(12, 2)
  irrf                    Decimal        @default(0) @db.Decimal(12, 2)
  outrosProventos         Decimal        @default(0) @db.Decimal(12, 2)
  outrosDescontos         Decimal        @default(0) @db.Decimal(12, 2)
  totalProventos          Decimal        @db.Decimal(12, 2)
  totalDescontos          Decimal        @db.Decimal(12, 2)
  liquido                 Decimal        @db.Decimal(12, 2)
  observacoes             String?

  @@index([cpf])
  @@index([folhaId])
}

model AuditFlag {
  id                String         @id @default(cuid())
  folhaId           String
  folha             FolhaPagamento @relation(fields: [folhaId], references: [id], onDelete: Cascade)
  cpf               String?
  regra             String
  gravidade         Gravidade
  descricao         String
  valorAtual        Decimal?       @db.Decimal(12, 2)
  valorCorreto      Decimal?       @db.Decimal(12, 2)
  economiaPotencial Decimal?       @db.Decimal(12, 2)
  acaoSugerida      String?
  createdAt         DateTime       @default(now())

  @@index([folhaId])
  @@index([gravidade])
}

model ConfiguracaoAuditoria {
  id         String   @id @default(cuid())
  regra      String   @unique
  ativo      Boolean  @default(true)
  parametros Json
  updatedAt  DateTime @updatedAt
}
```

**Step 2: Run migration**

```bash
cd C:/Users/bruno/auditor-folha/backend
npx prisma migrate dev --name init
```

Expected: Migration created successfully, tables exist in `auditor_folha` database.

**Step 3: Commit**

```bash
cd C:/Users/bruno/auditor-folha
git add -A
git commit -m "feat: add prisma schema with all models"
```

---

## Task 3: Backend Core — Config, Lib, Server

**Files:**
- Create: `backend/src/config/env.ts`
- Create: `backend/src/lib/logger.ts`
- Create: `backend/src/lib/prisma.ts`
- Create: `backend/src/api/middleware/error-handler.ts`
- Create: `backend/src/server.ts`

**Step 1: Create `config/env.ts`**

Uses Zod to validate env vars — same pattern as LicitaBrasil.

```ts
// backend/src/config/env.ts
import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const envSchema = z.object({
  DATABASE_URL: z.string(),
  PORT: z.coerce.number().default(3002),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  CORS_ORIGIN: z.string().default('http://localhost:5174'),
  LOG_LEVEL: z.string().default('info'),
});

export const env = envSchema.parse(process.env);
```

**Step 2: Create `lib/logger.ts`**

```ts
// backend/src/lib/logger.ts
import pino from 'pino';
import { env } from '../config/env.js';

export const logger = pino({
  level: env.LOG_LEVEL,
  transport: env.NODE_ENV === 'development'
    ? { target: 'pino-pretty', options: { colorize: true, translateTime: 'SYS:standard' } }
    : undefined,
});
```

**Step 3: Create `lib/prisma.ts`**

```ts
// backend/src/lib/prisma.ts
import { PrismaClient } from '@prisma/client';
import { env } from '../config/env.js';

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

export const prisma = globalForPrisma.prisma ?? new PrismaClient({
  log: env.NODE_ENV === 'development' ? ['error', 'warn'] : ['error'],
});

if (env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
```

**Step 4: Create `api/middleware/error-handler.ts`**

```ts
// backend/src/api/middleware/error-handler.ts
import { Request, Response, NextFunction } from 'express';
import { ZodError } from 'zod';
import { logger } from '../../lib/logger.js';

export class AppError extends Error {
  constructor(public statusCode: number, message: string) {
    super(message);
    this.name = 'AppError';
  }
}

export function errorHandler(err: Error, _req: Request, res: Response, _next: NextFunction): void {
  logger.error({ err }, 'Unhandled error');

  if (err instanceof AppError) {
    res.status(err.statusCode).json({ error: err.message });
    return;
  }
  if (err instanceof ZodError) {
    res.status(400).json({ error: 'Dados invalidos', details: err.errors });
    return;
  }
  res.status(500).json({ error: 'Erro interno do servidor' });
}
```

**Step 5: Create `server.ts`**

```ts
// backend/src/server.ts
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import compression from 'compression';
import pinoHttp from 'pino-http';
import { env } from './config/env.js';
import { logger } from './lib/logger.js';
import { prisma } from './lib/prisma.js';
import { errorHandler } from './api/middleware/error-handler.js';

const app = express();

app.use(pinoHttp({ logger }));
app.use(helmet());
app.use(cors({ origin: env.CORS_ORIGIN, credentials: true }));
app.use(compression());
app.use(express.json({ limit: '10mb' }));

// Health check
app.get('/api/health', async (_req, res) => {
  try {
    await prisma.$queryRaw`SELECT 1`;
    res.json({ status: 'ok', timestamp: new Date().toISOString() });
  } catch {
    res.status(503).json({ status: 'error', message: 'Database unavailable' });
  }
});

// Routes will be mounted here in subsequent tasks

app.use(errorHandler);

const server = app.listen(env.PORT, () => {
  logger.info(`Auditor Folha backend running on port ${env.PORT}`);
});

process.on('SIGTERM', async () => {
  server.close();
  await prisma.$disconnect();
  process.exit(0);
});

export { app };
```

**Step 6: Create uploads directory**

```bash
mkdir -p C:/Users/bruno/auditor-folha/backend/uploads
```

**Step 7: Verify server starts**

```bash
cd C:/Users/bruno/auditor-folha/backend && npm run dev
```

Expected: "Auditor Folha backend running on port 3002". Hit `http://localhost:3002/api/health` and get `{ "status": "ok" }`. Stop the server.

**Step 8: Commit**

```bash
git add -A && git commit -m "feat: add backend core (server, config, logger, prisma, error handler)"
```

---

## Task 4: Rubrica Mapper Service

**Files:**
- Create: `backend/src/api/services/rubrica-mapper.ts`
- Create: `backend/tests/rubrica-mapper.test.ts`

**Step 1: Write failing test**

```ts
// backend/tests/rubrica-mapper.test.ts
import { describe, it, expect } from 'vitest';
import { mapRubrica, TipoRubrica } from '../src/api/services/rubrica-mapper.js';

describe('mapRubrica', () => {
  it('maps "SALARIO BASE" to salarioBase provento', () => {
    const result = mapRubrica('SALARIO BASE');
    expect(result).toEqual({ campo: 'salarioBase', tipo: 'provento' });
  });

  it('maps "H.E. 50%" to horasExtras50 provento', () => {
    const result = mapRubrica('H.E. 50%');
    expect(result).toEqual({ campo: 'horasExtras50', tipo: 'provento' });
  });

  it('maps "HORA EXTRA 100%" to horasExtras100 provento', () => {
    const result = mapRubrica('HORA EXTRA 100%');
    expect(result).toEqual({ campo: 'horasExtras100', tipo: 'provento' });
  });

  it('maps "ADICIONAL NOTURNO" to adicionalNoturno provento', () => {
    const result = mapRubrica('ADICIONAL NOTURNO');
    expect(result).toEqual({ campo: 'adicionalNoturno', tipo: 'provento' });
  });

  it('maps "INSALUBRIDADE" to adicionalInsalubridade provento', () => {
    const result = mapRubrica('INSALUBRIDADE');
    expect(result).toEqual({ campo: 'adicionalInsalubridade', tipo: 'provento' });
  });

  it('maps "PERICULOSIDADE" to adicionalPericulosidade provento', () => {
    const result = mapRubrica('PERICULOSIDADE');
    expect(result).toEqual({ campo: 'adicionalPericulosidade', tipo: 'provento' });
  });

  it('maps "INSS" to inss desconto', () => {
    const result = mapRubrica('INSS');
    expect(result).toEqual({ campo: 'inss', tipo: 'desconto' });
  });

  it('maps "I.R.R.F." to irrf desconto', () => {
    const result = mapRubrica('I.R.R.F.');
    expect(result).toEqual({ campo: 'irrf', tipo: 'desconto' });
  });

  it('maps "VALE TRANSPORTE" to valeTransporte desconto', () => {
    const result = mapRubrica('VALE TRANSPORTE');
    expect(result).toEqual({ campo: 'valeTransporte', tipo: 'desconto' });
  });

  it('maps "V.A." to valeAlimentacao desconto', () => {
    const result = mapRubrica('V.A.');
    expect(result).toEqual({ campo: 'valeAlimentacao', tipo: 'desconto' });
  });

  it('maps "DESC. FALTAS" to faltasDesconto desconto', () => {
    const result = mapRubrica('DESC. FALTAS');
    expect(result).toEqual({ campo: 'faltasDesconto', tipo: 'desconto' });
  });

  it('maps "DSR S/ FALTAS" to dsrDesconto desconto', () => {
    const result = mapRubrica('DSR S/ FALTAS');
    expect(result).toEqual({ campo: 'dsrDesconto', tipo: 'desconto' });
  });

  it('returns null for unknown rubricas', () => {
    const result = mapRubrica('AJUDA CUSTO ESPECIAL');
    expect(result).toBeNull();
  });

  it('is case-insensitive', () => {
    const result = mapRubrica('salario base');
    expect(result).toEqual({ campo: 'salarioBase', tipo: 'provento' });
  });
});
```

**Step 2: Run test to verify it fails**

```bash
cd C:/Users/bruno/auditor-folha/backend && npx vitest run tests/rubrica-mapper.test.ts
```

Expected: FAIL — module not found.

**Step 3: Implement rubrica mapper**

```ts
// backend/src/api/services/rubrica-mapper.ts

export type TipoRubrica = 'provento' | 'desconto';

export interface RubricaMapping {
  campo: string;
  tipo: TipoRubrica;
}

// Each entry: [regex pattern, field name, type]
const RUBRICA_MAP: Array<[RegExp, string, TipoRubrica]> = [
  // Proventos
  [/sal[aá]rio\s*base/i, 'salarioBase', 'provento'],
  [/h\.?e\.?\s*50/i, 'horasExtras50', 'provento'],
  [/hora\s*extra\s*50/i, 'horasExtras50', 'provento'],
  [/h\.?e\.?\s*100/i, 'horasExtras100', 'provento'],
  [/hora\s*extra\s*100/i, 'horasExtras100', 'provento'],
  [/adic\.?\s*noturno|adicional\s*noturno/i, 'adicionalNoturno', 'provento'],
  [/insalubri/i, 'adicionalInsalubridade', 'provento'],
  [/periculosi/i, 'adicionalPericulosidade', 'provento'],

  // Descontos
  [/^inss$/i, 'inss', 'desconto'],
  [/i\.?n\.?s\.?s/i, 'inss', 'desconto'],
  [/i\.?r\.?r\.?f/i, 'irrf', 'desconto'],
  [/irrf/i, 'irrf', 'desconto'],
  [/vale\s*transporte|v\.?\s*t\.?$/i, 'valeTransporte', 'desconto'],
  [/vale\s*aliment|v\.?\s*a\.?$/i, 'valeAlimentacao', 'desconto'],
  [/desc\.?\s*falta|falta/i, 'faltasDesconto', 'desconto'],
  [/dsr\s*s\/?\s*falta|dsr/i, 'dsrDesconto', 'desconto'],
];

export function mapRubrica(nome: string): RubricaMapping | null {
  const trimmed = nome.trim();
  for (const [pattern, campo, tipo] of RUBRICA_MAP) {
    if (pattern.test(trimmed)) {
      return { campo, tipo };
    }
  }
  return null;
}
```

**Step 4: Run test to verify it passes**

```bash
npx vitest run tests/rubrica-mapper.test.ts
```

Expected: All 14 tests PASS.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add rubrica mapper with tests"
```

---

## Task 5: PDF Parser Service (Node.js wrapper for Python pdfplumber)

**Files:**
- Create: `backend/src/api/services/pdf-parser.ts`
- Create: `backend/tests/pdf-parser.test.ts`
- Create: `backend/tests/fixtures/folha-sample.json`

**Important:** The Node.js `pdf-parser.ts` is a thin wrapper that calls the Python `extract_pdf.py` script via `execFile()` (no shell — prevents injection). The Python script does the heavy lifting with pdfplumber. The regex patterns in the Python script are **starter patterns** — they MUST be calibrated with real PDFs.

**Step 1: Create a test fixture with expected JSON output**

This simulates what the Python script would return for a sample PDF.

```json
// backend/tests/fixtures/folha-sample.json
[
  {
    "nome": "JOAO DA SILVA",
    "cpf": "12345678900",
    "cargo": "AUXILIAR DE LIMPEZA",
    "salarioBase": 1412.00,
    "horasNormais": 0, "horasExtras50": 211.80, "horasExtras100": 0,
    "adicionalNoturno": 282.40, "adicionalInsalubridade": 0, "adicionalPericulosidade": 0,
    "faltasDias": 0, "faltasDesconto": 0, "atestadosDias": 0, "dsrDesconto": 0,
    "valeTransporte": 84.72, "valeAlimentacao": 0, "inss": 169.44, "irrf": 0,
    "outrosProventos": 0, "outrosDescontos": 0,
    "totalProventos": 1906.20, "totalDescontos": 254.16, "liquido": 1652.04,
    "observacoes": []
  },
  {
    "nome": "MARIA OLIVEIRA",
    "cpf": "98765432100",
    "cargo": "VIGILANTE",
    "salarioBase": 2100.00,
    "horasNormais": 0, "horasExtras50": 0, "horasExtras100": 0,
    "adicionalNoturno": 0, "adicionalInsalubridade": 0, "adicionalPericulosidade": 630.00,
    "faltasDias": 0, "faltasDesconto": 140.00, "atestadosDias": 0, "dsrDesconto": 70.00,
    "valeTransporte": 126.00, "valeAlimentacao": 50.00, "inss": 252.00, "irrf": 142.73,
    "outrosProventos": 0, "outrosDescontos": 0,
    "totalProventos": 2730.00, "totalDescontos": 780.73, "liquido": 1949.27,
    "observacoes": []
  }
]
```

**Step 2: Write failing test**

```ts
// backend/tests/pdf-parser.test.ts
import { describe, it, expect, vi } from 'vitest';
import { extractFromPdf, type ParsedEmployee } from '../src/api/services/pdf-parser.js';
import { readFileSync } from 'fs';
import path from 'path';

// Mock execFile to return fixture data instead of calling Python
vi.mock('child_process', () => ({
  execFile: vi.fn((_cmd: string, _args: string[], _opts: any, cb: Function) => {
    const fixture = readFileSync(
      path.join(import.meta.dirname, 'fixtures/folha-sample.json'),
      'utf-8'
    );
    cb(null, fixture, '');
  }),
}));

describe('extractFromPdf', () => {
  it('parses Python script output into ParsedEmployee[]', async () => {
    const result = await extractFromPdf('/fake/path.pdf');
    expect(result).toHaveLength(2);
  });

  it('extracts first employee correctly', async () => {
    const result = await extractFromPdf('/fake/path.pdf');
    expect(result[0].nome).toBe('JOAO DA SILVA');
    expect(result[0].cpf).toBe('12345678900');
    expect(result[0].cargo).toBe('AUXILIAR DE LIMPEZA');
    expect(result[0].salarioBase).toBe(1412.00);
    expect(result[0].horasExtras50).toBe(211.80);
    expect(result[0].totalProventos).toBe(1906.20);
    expect(result[0].liquido).toBe(1652.04);
  });

  it('extracts second employee with faltas and DSR', async () => {
    const result = await extractFromPdf('/fake/path.pdf');
    expect(result[1].nome).toBe('MARIA OLIVEIRA');
    expect(result[1].adicionalPericulosidade).toBe(630.00);
    expect(result[1].faltasDesconto).toBe(140.00);
    expect(result[1].dsrDesconto).toBe(70.00);
  });
});
```

**Step 3: Run test to verify it fails**

```bash
npx vitest run tests/pdf-parser.test.ts
```

Expected: FAIL — module not found.

**Step 4: Implement PDF parser (Node.js wrapper)**

```ts
// backend/src/api/services/pdf-parser.ts
import { execFile } from 'child_process';
import path from 'path';

export interface ParsedEmployee {
  nome: string;
  cpf: string;
  cargo: string;
  salarioBase: number;
  horasNormais: number;
  horasExtras50: number;
  horasExtras100: number;
  adicionalNoturno: number;
  adicionalInsalubridade: number;
  adicionalPericulosidade: number;
  faltasDias: number;
  faltasDesconto: number;
  atestadosDias: number;
  dsrDesconto: number;
  valeTransporte: number;
  valeAlimentacao: number;
  inss: number;
  irrf: number;
  outrosProventos: number;
  outrosDescontos: number;
  totalProventos: number;
  totalDescontos: number;
  liquido: number;
  observacoes: string[];
}

const PYTHON_SCRIPT = path.resolve('scripts', 'extract_pdf.py');

export function extractFromPdf(pdfPath: string): Promise<ParsedEmployee[]> {
  return new Promise((resolve, reject) => {
    // execFile (not exec) — no shell, prevents command injection
    execFile('python', [PYTHON_SCRIPT, pdfPath], { maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        reject(new Error(`Python PDF extraction failed: ${stderr || err.message}`));
        return;
      }

      try {
        const parsed = JSON.parse(stdout);

        // Check for error response from Python
        if (parsed.error) {
          reject(new Error(`PDF extraction error: ${parsed.error}`));
          return;
        }

        // Validate it's an array
        if (!Array.isArray(parsed)) {
          reject(new Error('PDF extraction returned invalid format'));
          return;
        }

        resolve(parsed as ParsedEmployee[]);
      } catch (parseErr) {
        reject(new Error(`Failed to parse Python output: ${(parseErr as Error).message}`));
      }
    });
  });
}
```

**Step 5: Run test to verify it passes**

```bash
npx vitest run tests/pdf-parser.test.ts
```

Expected: All tests PASS.

**Step 6: Commit**

```bash
git add -A && git commit -m "feat: add PDF parser wrapper for pdfplumber extraction"
```

---

## Task 6: Audit Engine Service

**Files:**
- Create: `backend/src/api/services/audit-engine.ts`
- Create: `backend/tests/audit-engine.test.ts`

**Step 1: Write failing tests for critical rules**

```ts
// backend/tests/audit-engine.test.ts
import { describe, it, expect } from 'vitest';
import {
  runAudit,
  AuditResult,
  DEFAULT_PARAMS,
  type EmployeeData,
  type FolhaData,
} from '../src/api/services/audit-engine.js';

function makeEmployee(overrides: Partial<EmployeeData> = {}): EmployeeData {
  return {
    cpf: '12345678900',
    nome: 'JOAO DA SILVA',
    cargo: 'AUXILIAR DE LIMPEZA',
    salarioBase: 1412,
    horasExtras50: 0, horasExtras100: 0,
    adicionalNoturno: 0, adicionalInsalubridade: 0, adicionalPericulosidade: 0,
    faltasDias: 0, faltasDesconto: 0, atestadosDias: 0, dsrDesconto: 0,
    valeTransporte: 84.72, valeAlimentacao: 0,
    outrosProventos: 0, totalProventos: 1412, totalDescontos: 84.72, liquido: 1327.28,
    ...overrides,
  };
}

function makeFolha(overrides: Partial<FolhaData> = {}): FolhaData {
  return {
    mesReferencia: '2024-06',
    totalProventos: 50000,
    totalDescontos: 12000,
    totalLiquido: 38000,
    ...overrides,
  };
}

describe('Audit Engine — Critical Rules', () => {
  it('flags FALTAS_EXCESSIVAS when faltas > limit', () => {
    const emp = makeEmployee({ faltasDias: 6 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    const flag = result.find(f => f.regra === 'FALTAS_EXCESSIVAS');
    expect(flag).toBeDefined();
    expect(flag!.gravidade).toBe('CRITICO');
  });

  it('does NOT flag FALTAS_EXCESSIVAS when faltas <= limit', () => {
    const emp = makeEmployee({ faltasDias: 5 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    expect(result.find(f => f.regra === 'FALTAS_EXCESSIVAS')).toBeUndefined();
  });

  it('flags HE_ACIMA_LIMITE when horasExtras50 + horasExtras100 > limit', () => {
    const emp = makeEmployee({ horasExtras50: 30, horasExtras100: 15 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    const flag = result.find(f => f.regra === 'HE_ACIMA_LIMITE');
    expect(flag).toBeDefined();
    expect(flag!.gravidade).toBe('CRITICO');
  });

  it('does NOT flag HE_ACIMA_LIMITE when total HE <= limit', () => {
    const emp = makeEmployee({ horasExtras50: 20, horasExtras100: 10 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    expect(result.find(f => f.regra === 'HE_ACIMA_LIMITE')).toBeUndefined();
  });
});

describe('Audit Engine — Alert Rules', () => {
  it('flags ACUMULO_ADICIONAIS when both insalubridade + periculosidade > 0', () => {
    const emp = makeEmployee({ adicionalInsalubridade: 200, adicionalPericulosidade: 300 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    const flag = result.find(f => f.regra === 'ACUMULO_ADICIONAIS');
    expect(flag).toBeDefined();
    expect(flag!.gravidade).toBe('ALERTA');
  });

  it('flags DSR_NAO_DESCONTADO when faltas > 0 but dsrDesconto == 0', () => {
    const emp = makeEmployee({ faltasDias: 2, dsrDesconto: 0 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    const flag = result.find(f => f.regra === 'DSR_NAO_DESCONTADO');
    expect(flag).toBeDefined();
    expect(flag!.gravidade).toBe('ALERTA');
  });

  it('does NOT flag DSR_NAO_DESCONTADO when dsrDesconto > 0', () => {
    const emp = makeEmployee({ faltasDias: 2, dsrDesconto: 70 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    expect(result.find(f => f.regra === 'DSR_NAO_DESCONTADO')).toBeUndefined();
  });

  it('flags HE_100_EXCESSIVA when horasExtras100 > limit', () => {
    const emp = makeEmployee({ horasExtras100: 20 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    const flag = result.find(f => f.regra === 'HE_100_EXCESSIVA');
    expect(flag).toBeDefined();
    expect(flag!.gravidade).toBe('ALERTA');
  });
});

describe('Audit Engine — Opportunity Rules', () => {
  it('flags OUTROS_PROVENTOS_ALTO when outrosProventos > threshold % of salarioBase', () => {
    const emp = makeEmployee({ salarioBase: 1412, outrosProventos: 200 });
    const result = runAudit([emp], makeFolha(), DEFAULT_PARAMS);
    const flag = result.find(f => f.regra === 'OUTROS_PROVENTOS_ALTO');
    expect(flag).toBeDefined();
    expect(flag!.gravidade).toBe('OPORTUNIDADE');
  });
});

describe('Audit Engine — Custom params', () => {
  it('respects custom limiteFaltas param', () => {
    const emp = makeEmployee({ faltasDias: 8 });
    const params = { ...DEFAULT_PARAMS, FALTAS_EXCESSIVAS: { limiteFaltas: 10 } };
    const result = runAudit([emp], makeFolha(), params);
    expect(result.find(f => f.regra === 'FALTAS_EXCESSIVAS')).toBeUndefined();
  });
});
```

**Step 2: Run test to verify it fails**

```bash
npx vitest run tests/audit-engine.test.ts
```

Expected: FAIL — module not found.

**Step 3: Implement audit engine**

```ts
// backend/src/api/services/audit-engine.ts

export interface EmployeeData {
  cpf: string;
  nome: string;
  cargo: string;
  salarioBase: number;
  horasExtras50: number;
  horasExtras100: number;
  adicionalNoturno: number;
  adicionalInsalubridade: number;
  adicionalPericulosidade: number;
  faltasDias: number;
  faltasDesconto: number;
  atestadosDias: number;
  dsrDesconto: number;
  valeTransporte: number;
  valeAlimentacao: number;
  outrosProventos: number;
  totalProventos: number;
  totalDescontos: number;
  liquido: number;
}

export interface FolhaData {
  mesReferencia: string;
  totalProventos: number;
  totalDescontos: number;
  totalLiquido: number;
}

export interface AuditResult {
  cpf: string | null;
  regra: string;
  gravidade: 'CRITICO' | 'ALERTA' | 'OPORTUNIDADE';
  descricao: string;
  valorAtual?: number;
  valorCorreto?: number;
  economiaPotencial?: number;
  acaoSugerida?: string;
}

export const DEFAULT_PARAMS: Record<string, Record<string, number>> = {
  FALTAS_EXCESSIVAS:   { limiteFaltas: 5 },
  HE_ACIMA_LIMITE:     { limiteHE: 40 },
  HE_100_EXCESSIVA:    { limiteHE100: 16 },
  VARIACAO_FOLHA:      { limiteVariacao: 8 },
  OUTROS_PROVENTOS_ALTO: { limitePercentual: 10 },
};

type RuleFn = (emp: EmployeeData, params: Record<string, number>) => AuditResult | null;

const RULES: Array<{ codigo: string; gravidade: AuditResult['gravidade']; check: RuleFn }> = [
  // CRITICO
  {
    codigo: 'FALTAS_EXCESSIVAS',
    gravidade: 'CRITICO',
    check: (emp, params) => {
      const limite = params.limiteFaltas ?? 5;
      if (emp.faltasDias > limite) {
        return {
          cpf: emp.cpf, regra: 'FALTAS_EXCESSIVAS', gravidade: 'CRITICO',
          descricao: `${emp.nome} com ${emp.faltasDias} faltas (limite: ${limite})`,
          valorAtual: emp.faltasDias,
          acaoSugerida: 'Verificar se cabe advertencia, suspensao ou justa causa',
        };
      }
      return null;
    },
  },
  {
    codigo: 'HE_ACIMA_LIMITE',
    gravidade: 'CRITICO',
    check: (emp, params) => {
      const limite = params.limiteHE ?? 40;
      const totalHE = emp.horasExtras50 + emp.horasExtras100;
      if (totalHE > limite) {
        return {
          cpf: emp.cpf, regra: 'HE_ACIMA_LIMITE', gravidade: 'CRITICO',
          descricao: `${emp.nome} com R$ ${totalHE.toFixed(2)} em horas extras (limite: R$ ${limite})`,
          valorAtual: totalHE, valorCorreto: limite,
          economiaPotencial: totalHE - limite,
          acaoSugerida: 'Verificar necessidade real ou falha de escala',
        };
      }
      return null;
    },
  },
  // ALERTA
  {
    codigo: 'ACUMULO_ADICIONAIS',
    gravidade: 'ALERTA',
    check: (emp) => {
      if (emp.adicionalInsalubridade > 0 && emp.adicionalPericulosidade > 0) {
        const menor = Math.min(emp.adicionalInsalubridade, emp.adicionalPericulosidade);
        return {
          cpf: emp.cpf, regra: 'ACUMULO_ADICIONAIS', gravidade: 'ALERTA',
          descricao: `${emp.nome} recebendo insalubridade (${emp.adicionalInsalubridade}) e periculosidade (${emp.adicionalPericulosidade}) simultaneamente`,
          economiaPotencial: menor,
          acaoSugerida: 'Corrigir: CLT veda acumulo, funcionario deve optar pelo mais vantajoso',
        };
      }
      return null;
    },
  },
  {
    codigo: 'DSR_NAO_DESCONTADO',
    gravidade: 'ALERTA',
    check: (emp) => {
      if (emp.faltasDias > 0 && emp.dsrDesconto === 0) {
        return {
          cpf: emp.cpf, regra: 'DSR_NAO_DESCONTADO', gravidade: 'ALERTA',
          descricao: `${emp.nome} com ${emp.faltasDias} falta(s) mas sem desconto de DSR`,
          acaoSugerida: 'Recalcular e ajustar desconto de DSR',
        };
      }
      return null;
    },
  },
  {
    codigo: 'HE_100_EXCESSIVA',
    gravidade: 'ALERTA',
    check: (emp, params) => {
      const limite = params.limiteHE100 ?? 16;
      if (emp.horasExtras100 > limite) {
        return {
          cpf: emp.cpf, regra: 'HE_100_EXCESSIVA', gravidade: 'ALERTA',
          descricao: `${emp.nome} com R$ ${emp.horasExtras100.toFixed(2)} em HE 100% (limite: R$ ${limite})`,
          valorAtual: emp.horasExtras100,
          acaoSugerida: 'Verificar autorizacao formal para HE em feriados/domingos',
        };
      }
      return null;
    },
  },
  // OPORTUNIDADE
  {
    codigo: 'OUTROS_PROVENTOS_ALTO',
    gravidade: 'OPORTUNIDADE',
    check: (emp, params) => {
      const limite = params.limitePercentual ?? 10;
      const percentual = emp.salarioBase > 0 ? (emp.outrosProventos / emp.salarioBase) * 100 : 0;
      if (percentual > limite) {
        return {
          cpf: emp.cpf, regra: 'OUTROS_PROVENTOS_ALTO', gravidade: 'OPORTUNIDADE',
          descricao: `${emp.nome} com "outros proventos" de R$ ${emp.outrosProventos.toFixed(2)} (${percentual.toFixed(1)}% do salario base)`,
          valorAtual: emp.outrosProventos,
          acaoSugerida: 'Identificar e documentar cada rubrica',
        };
      }
      return null;
    },
  },
];

export function runAudit(
  employees: EmployeeData[],
  _folha: FolhaData,
  params: Record<string, Record<string, number>>,
): AuditResult[] {
  const flags: AuditResult[] = [];

  for (const emp of employees) {
    for (const rule of RULES) {
      const ruleParams = params[rule.codigo] ?? {};
      const flag = rule.check(emp, ruleParams);
      if (flag) flags.push(flag);
    }
  }

  return flags;
}
```

**Step 4: Run tests**

```bash
npx vitest run tests/audit-engine.test.ts
```

Expected: All tests PASS.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add audit engine with 6 rules and tests"
```

---

## Task 7: Backend Routes — Contratos + CCT

**Files:**
- Create: `backend/src/api/routes/contratos.ts`
- Create: `backend/src/api/routes/cct.ts`
- Modify: `backend/src/server.ts` — mount routes

**Step 1: Create contratos route**

```ts
// backend/src/api/routes/contratos.ts
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { prisma } from '../../lib/prisma.js';
import { AppError } from '../middleware/error-handler.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

const createContratoSchema = z.object({
  codigo: z.string().min(1),
  nome: z.string().min(1),
  cctId: z.string().optional(),
});

// GET /api/contratos
router.get('/', asyncHandler(async (_req, res) => {
  const contratos = await prisma.contrato.findMany({
    include: { cct: true, _count: { select: { folhas: true } } },
    orderBy: { createdAt: 'desc' },
  });
  res.json(contratos);
}));

// POST /api/contratos
router.post('/', asyncHandler(async (req, res) => {
  const data = createContratoSchema.parse(req.body);
  const contrato = await prisma.contrato.create({ data });
  res.status(201).json(contrato);
}));

// GET /api/contratos/:id
router.get('/:id', asyncHandler(async (req, res) => {
  const contrato = await prisma.contrato.findUnique({
    where: { id: req.params.id },
    include: { cct: { include: { pisos: true } }, folhas: { orderBy: { mesReferencia: 'desc' } } },
  });
  if (!contrato) throw new AppError(404, 'Contrato nao encontrado');
  res.json(contrato);
}));

// DELETE /api/contratos/:id
router.delete('/:id', asyncHandler(async (req, res) => {
  await prisma.contrato.delete({ where: { id: req.params.id } });
  res.status(204).send();
}));

export { router as contratosRouter };
```

**Step 2: Create CCT route**

```ts
// backend/src/api/routes/cct.ts
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { prisma } from '../../lib/prisma.js';
import { AppError } from '../middleware/error-handler.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

const createCCTSchema = z.object({
  nome: z.string().min(1),
  sindicato: z.string().min(1),
  vigenciaInicio: z.coerce.date(),
  vigenciaFim: z.coerce.date(),
});

const createPisoSchema = z.object({
  cargo: z.string().min(1),
  pisoSalarial: z.number().positive(),
  adicionalInsalubridade: z.number().optional(),
  adicionalPericulosidade: z.number().optional(),
  adicionalNoturno: z.number().optional(),
});

// GET /api/cct
router.get('/', asyncHandler(async (_req, res) => {
  const ccts = await prisma.convencaoColetiva.findMany({
    include: { pisos: true, _count: { select: { contratos: true } } },
    orderBy: { vigenciaFim: 'desc' },
  });
  res.json(ccts);
}));

// POST /api/cct
router.post('/', asyncHandler(async (req, res) => {
  const data = createCCTSchema.parse(req.body);
  const cct = await prisma.convencaoColetiva.create({ data });
  res.status(201).json(cct);
}));

// POST /api/cct/:id/pisos
router.post('/:id/pisos', asyncHandler(async (req, res) => {
  const data = createPisoSchema.parse(req.body);
  const piso = await prisma.pisoCCT.create({
    data: { ...data, cctId: req.params.id },
  });
  res.status(201).json(piso);
}));

// DELETE /api/cct/:id
router.delete('/:id', asyncHandler(async (req, res) => {
  await prisma.convencaoColetiva.delete({ where: { id: req.params.id } });
  res.status(204).send();
}));

export { router as cctRouter };
```

**Step 3: Mount routes in `server.ts`**

Add these imports and route mounts after the health check:

```ts
// Add to server.ts imports:
import { contratosRouter } from './api/routes/contratos.js';
import { cctRouter } from './api/routes/cct.js';

// Add after health check:
app.use('/api/contratos', contratosRouter);
app.use('/api/cct', cctRouter);
```

**Step 4: Verify server starts and routes respond**

```bash
cd C:/Users/bruno/auditor-folha/backend && npm run dev
# In another terminal:
curl http://localhost:3002/api/contratos
# Expected: []
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add contratos and CCT routes"
```

---

## Task 8: Backend Routes — Upload + Folhas + Auditoria

**Files:**
- Create: `backend/src/api/routes/upload.ts`
- Create: `backend/src/api/routes/folhas.ts`
- Create: `backend/src/api/routes/auditoria.ts`
- Modify: `backend/src/server.ts` — mount routes

**Step 1: Create upload route**

This is the core route: receives PDF, extracts data, saves to DB, runs audit.

```ts
// backend/src/api/routes/upload.ts
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import multer from 'multer';
import path from 'path';
import { prisma } from '../../lib/prisma.js';
import { logger } from '../../lib/logger.js';
import { extractFromPdf } from '../services/pdf-parser.js';
import { runAudit, DEFAULT_PARAMS, type EmployeeData } from '../services/audit-engine.js';
import { AppError } from '../middleware/error-handler.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

const uploadsDir = path.resolve('uploads');

const storage = multer.diskStorage({
  destination: uploadsDir,
  filename: (_req, file, cb) => {
    const uniqueName = `${Date.now()}-${file.originalname}`;
    cb(null, uniqueName);
  },
});
const upload = multer({ storage, fileFilter: (_req, file, cb) => {
  cb(null, file.mimetype === 'application/pdf');
}});

const uploadBodySchema = z.object({
  contratoId: z.string().min(1),
  mesReferencia: z.string().regex(/^\d{4}-\d{2}$/),
});

// POST /api/upload
router.post('/', upload.single('pdf'), asyncHandler(async (req, res) => {
  if (!req.file) throw new AppError(400, 'Arquivo PDF obrigatorio');

  const { contratoId, mesReferencia } = uploadBodySchema.parse(req.body);

  // Check contract exists
  const contrato = await prisma.contrato.findUnique({ where: { id: contratoId } });
  if (!contrato) throw new AppError(404, 'Contrato nao encontrado');

  // Check duplicate
  const existing = await prisma.folhaPagamento.findUnique({
    where: { contratoId_mesReferencia: { contratoId, mesReferencia } },
  });
  if (existing) throw new AppError(409, `Folha de ${mesReferencia} ja existe para este contrato`);

  // Create folha record
  const folha = await prisma.folhaPagamento.create({
    data: {
      contratoId,
      mesReferencia,
      arquivoPdf: req.file.filename,
      status: 'PROCESSANDO',
    },
  });

  try {
    // Extract employees from PDF via Python pdfplumber
    const parsed = await extractFromPdf(req.file.path);
    if (parsed.length === 0) {
      await prisma.folhaPagamento.update({
        where: { id: folha.id },
        data: { status: 'ERRO', erroMsg: 'Nenhum funcionario encontrado no PDF' },
      });
      throw new AppError(422, 'Nenhum funcionario encontrado no PDF. Verifique o formato.');
    }

    // Save employees
    for (const emp of parsed) {
      await prisma.funcionarioFolha.create({
        data: {
          folhaId: folha.id,
          nome: emp.nome,
          cpf: emp.cpf,
          cargo: emp.cargo,
          salarioBase: emp.salarioBase,
          horasNormais: emp.horasNormais,
          horasExtras50: emp.horasExtras50,
          horasExtras100: emp.horasExtras100,
          adicionalNoturno: emp.adicionalNoturno,
          adicionalInsalubridade: emp.adicionalInsalubridade,
          adicionalPericulosidade: emp.adicionalPericulosidade,
          faltasDias: emp.faltasDias,
          faltasDesconto: emp.faltasDesconto,
          atestadosDias: emp.atestadosDias,
          dsrDesconto: emp.dsrDesconto,
          valeTransporte: emp.valeTransporte,
          valeAlimentacao: emp.valeAlimentacao,
          inss: emp.inss,
          irrf: emp.irrf,
          outrosProventos: emp.outrosProventos,
          outrosDescontos: emp.outrosDescontos,
          totalProventos: emp.totalProventos,
          totalDescontos: emp.totalDescontos,
          liquido: emp.liquido,
          observacoes: emp.observacoes.length > 0 ? emp.observacoes.join('; ') : null,
        },
      });
    }

    // Compute folha totals
    const totalProventos = parsed.reduce((s, e) => s + e.totalProventos, 0);
    const totalDescontos = parsed.reduce((s, e) => s + e.totalDescontos, 0);
    const totalLiquido = parsed.reduce((s, e) => s + e.liquido, 0);

    // Run audit
    const configRows = await prisma.configuracaoAuditoria.findMany();
    const params: Record<string, Record<string, number>> = { ...DEFAULT_PARAMS };
    for (const cfg of configRows) {
      if (!cfg.ativo) continue;
      params[cfg.regra] = cfg.parametros as Record<string, number>;
    }

    const employeeData: EmployeeData[] = parsed;
    const flags = runAudit(employeeData, {
      mesReferencia, totalProventos, totalDescontos, totalLiquido,
    }, params);

    // Save flags
    for (const flag of flags) {
      await prisma.auditFlag.create({
        data: {
          folhaId: folha.id,
          cpf: flag.cpf,
          regra: flag.regra,
          gravidade: flag.gravidade,
          descricao: flag.descricao,
          valorAtual: flag.valorAtual,
          valorCorreto: flag.valorCorreto,
          economiaPotencial: flag.economiaPotencial,
          acaoSugerida: flag.acaoSugerida,
        },
      });
    }

    // Update folha status
    await prisma.folhaPagamento.update({
      where: { id: folha.id },
      data: {
        status: 'CONCLUIDO',
        totalProventos, totalDescontos, totalLiquido,
        processadoEm: new Date(),
      },
    });

    logger.info({ folhaId: folha.id, employees: parsed.length, flags: flags.length }, 'Folha processada');

    res.status(201).json({
      folhaId: folha.id,
      funcionarios: parsed.length,
      flags: flags.length,
      totalProventos, totalDescontos, totalLiquido,
    });

  } catch (err) {
    if (err instanceof AppError) throw err;
    logger.error({ err, folhaId: folha.id }, 'Erro ao processar PDF');
    await prisma.folhaPagamento.update({
      where: { id: folha.id },
      data: { status: 'ERRO', erroMsg: (err as Error).message },
    });
    throw new AppError(500, 'Erro ao processar o PDF');
  }
}));

export { router as uploadRouter };
```

**Step 2: Create folhas route**

```ts
// backend/src/api/routes/folhas.ts
import { Router, Request, Response, NextFunction } from 'express';
import { prisma } from '../../lib/prisma.js';
import { AppError } from '../middleware/error-handler.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

// GET /api/folhas
router.get('/', asyncHandler(async (req, res) => {
  const { contratoId, mesReferencia } = req.query;
  const where: any = {};
  if (contratoId) where.contratoId = contratoId;
  if (mesReferencia) where.mesReferencia = mesReferencia;

  const folhas = await prisma.folhaPagamento.findMany({
    where,
    include: {
      contrato: true,
      _count: { select: { funcionarios: true, flags: true } },
    },
    orderBy: { createdAt: 'desc' },
  });
  res.json(folhas);
}));

// GET /api/folhas/:id
router.get('/:id', asyncHandler(async (req, res) => {
  const folha = await prisma.folhaPagamento.findUnique({
    where: { id: req.params.id },
    include: {
      contrato: true,
      funcionarios: { orderBy: { nome: 'asc' } },
      flags: { orderBy: { gravidade: 'asc' } },
    },
  });
  if (!folha) throw new AppError(404, 'Folha nao encontrada');
  res.json(folha);
}));

// DELETE /api/folhas/:id
router.delete('/:id', asyncHandler(async (req, res) => {
  await prisma.folhaPagamento.delete({ where: { id: req.params.id } });
  res.status(204).send();
}));

export { router as folhasRouter };
```

**Step 3: Create auditoria route**

```ts
// backend/src/api/routes/auditoria.ts
import { Router, Request, Response, NextFunction } from 'express';
import { prisma } from '../../lib/prisma.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

// GET /api/auditoria/flags
router.get('/flags', asyncHandler(async (req, res) => {
  const { gravidade, contratoId, mesReferencia, regra } = req.query;

  const where: any = {};
  if (gravidade) where.gravidade = gravidade;
  if (regra) where.regra = regra;
  if (contratoId || mesReferencia) {
    where.folha = {};
    if (contratoId) where.folha.contratoId = contratoId;
    if (mesReferencia) where.folha.mesReferencia = mesReferencia;
  }

  const flags = await prisma.auditFlag.findMany({
    where,
    include: { folha: { include: { contrato: true } } },
    orderBy: [{ gravidade: 'asc' }, { createdAt: 'desc' }],
  });

  res.json(flags);
}));

// GET /api/auditoria/resumo
router.get('/resumo', asyncHandler(async (_req, res) => {
  const [critico, alerta, oportunidade] = await Promise.all([
    prisma.auditFlag.count({ where: { gravidade: 'CRITICO' } }),
    prisma.auditFlag.count({ where: { gravidade: 'ALERTA' } }),
    prisma.auditFlag.count({ where: { gravidade: 'OPORTUNIDADE' } }),
  ]);

  const economia = await prisma.auditFlag.aggregate({
    _sum: { economiaPotencial: true },
  });

  res.json({
    critico, alerta, oportunidade,
    total: critico + alerta + oportunidade,
    economiaPotencial: economia._sum.economiaPotencial ?? 0,
  });
}));

export { router as auditoriaRouter };
```

**Step 4: Mount routes in `server.ts`**

Add these imports and mounts:

```ts
import { uploadRouter } from './api/routes/upload.js';
import { folhasRouter } from './api/routes/folhas.js';
import { auditoriaRouter } from './api/routes/auditoria.js';

app.use('/api/upload', uploadRouter);
app.use('/api/folhas', folhasRouter);
app.use('/api/auditoria', auditoriaRouter);
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add upload, folhas, and auditoria routes"
```

---

## Task 9: Backend Routes — Configuracoes + Dashboard

**Files:**
- Create: `backend/src/api/routes/configuracoes.ts`
- Create: `backend/src/api/routes/dashboard.ts`
- Modify: `backend/src/server.ts` — mount routes

**Step 1: Create configuracoes route**

```ts
// backend/src/api/routes/configuracoes.ts
import { Router, Request, Response, NextFunction } from 'express';
import { z } from 'zod';
import { prisma } from '../../lib/prisma.js';
import { DEFAULT_PARAMS } from '../services/audit-engine.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

// GET /api/configuracoes — returns all rules with current params
router.get('/', asyncHandler(async (_req, res) => {
  const configs = await prisma.configuracaoAuditoria.findMany({ orderBy: { regra: 'asc' } });

  // Merge DB configs with defaults for rules that don't have a config row yet
  const allRules = Object.keys(DEFAULT_PARAMS);
  const result = allRules.map(regra => {
    const dbConfig = configs.find(c => c.regra === regra);
    return {
      regra,
      ativo: dbConfig?.ativo ?? true,
      parametros: dbConfig?.parametros ?? DEFAULT_PARAMS[regra],
      parametrosPadrao: DEFAULT_PARAMS[regra],
    };
  });

  res.json(result);
}));

const updateSchema = z.object({
  ativo: z.boolean().optional(),
  parametros: z.record(z.number()).optional(),
});

// PUT /api/configuracoes/:regra
router.put('/:regra', asyncHandler(async (req, res) => {
  const data = updateSchema.parse(req.body);
  const config = await prisma.configuracaoAuditoria.upsert({
    where: { regra: req.params.regra },
    update: { ...data, parametros: data.parametros ?? undefined },
    create: {
      regra: req.params.regra,
      ativo: data.ativo ?? true,
      parametros: data.parametros ?? DEFAULT_PARAMS[req.params.regra] ?? {},
    },
  });
  res.json(config);
}));

export { router as configuracoesRouter };
```

**Step 2: Create dashboard route**

```ts
// backend/src/api/routes/dashboard.ts
import { Router, Request, Response, NextFunction } from 'express';
import { prisma } from '../../lib/prisma.js';

const router = Router();

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;
function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => { fn(req, res, next).catch(next); };
}

// GET /api/dashboard
router.get('/', asyncHandler(async (_req, res) => {
  const [
    totalContratos,
    totalFolhas,
    flagsCritico,
    flagsAlerta,
    flagsOportunidade,
    economia,
    recentFolhas,
    topFlags,
  ] = await Promise.all([
    prisma.contrato.count(),
    prisma.folhaPagamento.count({ where: { status: 'CONCLUIDO' } }),
    prisma.auditFlag.count({ where: { gravidade: 'CRITICO' } }),
    prisma.auditFlag.count({ where: { gravidade: 'ALERTA' } }),
    prisma.auditFlag.count({ where: { gravidade: 'OPORTUNIDADE' } }),
    prisma.auditFlag.aggregate({ _sum: { economiaPotencial: true } }),
    prisma.folhaPagamento.findMany({
      take: 5,
      orderBy: { createdAt: 'desc' },
      include: { contrato: true, _count: { select: { funcionarios: true, flags: true } } },
    }),
    prisma.auditFlag.findMany({
      where: { gravidade: 'CRITICO' },
      take: 5,
      orderBy: { createdAt: 'desc' },
      include: { folha: { include: { contrato: true } } },
    }),
  ]);

  res.json({
    totalContratos,
    totalFolhas,
    flags: {
      critico: flagsCritico,
      alerta: flagsAlerta,
      oportunidade: flagsOportunidade,
      total: flagsCritico + flagsAlerta + flagsOportunidade,
    },
    economiaPotencial: economia._sum.economiaPotencial ?? 0,
    recentFolhas,
    topFlags,
  });
}));

export { router as dashboardRouter };
```

**Step 3: Mount routes in `server.ts`**

```ts
import { configuracoesRouter } from './api/routes/configuracoes.js';
import { dashboardRouter } from './api/routes/dashboard.js';

app.use('/api/configuracoes', configuracoesRouter);
app.use('/api/dashboard', dashboardRouter);
```

**Step 4: Verify all routes work**

```bash
npm run dev
# Test: curl http://localhost:3002/api/dashboard
# Expected: JSON with all zeros (no data yet)
```

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add configuracoes and dashboard routes"
```

---

## Task 10: Frontend Scaffolding

**Files:**
- Create: `C:/Users/bruno/auditor-folha/frontend/` (via Vite)
- Modify: `frontend/package.json` — add dependencies
- Create: `frontend/src/index.css`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/tsconfig.json`

**Step 1: Scaffold React + Vite project**

```bash
cd C:/Users/bruno/auditor-folha
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
```

**Step 2: Install dependencies**

```bash
npm install react-router-dom zustand lucide-react clsx tailwind-merge react-hot-toast react-dropzone
npm install -D tailwindcss @tailwindcss/vite
```

**Step 3: Configure `vite.config.ts`**

```ts
// frontend/vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5174,
    proxy: { '/api': { target: 'http://localhost:3002', changeOrigin: true } },
  },
});
```

**Step 4: Update `tsconfig.json` paths**

Add to `compilerOptions`:
```json
"baseUrl": ".",
"paths": { "@/*": ["./src/*"] }
```

**Step 5: Replace `index.css` with Tailwind v4 setup**

```css
/* frontend/src/index.css */
@import "tailwindcss";

@custom-variant dark (&:is(.dark *));

@theme {
  --color-background: hsl(var(--background));
  --color-foreground: hsl(var(--foreground));
  --color-primary: hsl(var(--primary));
  --color-primary-foreground: hsl(var(--primary-foreground));
  --color-muted: hsl(var(--muted));
  --color-muted-foreground: hsl(var(--muted-foreground));
  --color-border: hsl(var(--border));
  --color-card: hsl(var(--card));
  --color-destructive: hsl(var(--destructive));
  --color-success: hsl(var(--success));
  --color-warning: hsl(var(--warning));
}

:root {
  --background: 0 0% 100%;
  --foreground: 222.2 84% 4.9%;
  --primary: 217.2 91.2% 59.8%;
  --primary-foreground: 210 40% 98%;
  --muted: 210 40% 96%;
  --muted-foreground: 215.4 16.3% 46.9%;
  --border: 214.3 31.8% 91.4%;
  --card: 0 0% 100%;
  --destructive: 0 84.2% 60.2%;
  --success: 142 76% 36%;
  --warning: 38 92% 50%;
}

.dark {
  --background: 222.2 84% 4.9%;
  --foreground: 210 40% 98%;
  --primary: 217.2 91.2% 59.8%;
  --primary-foreground: 222.2 84% 4.9%;
  --muted: 217.2 32.6% 17.5%;
  --muted-foreground: 215 20.2% 65.1%;
  --border: 217.2 32.6% 17.5%;
  --card: 222.2 84% 6%;
  --destructive: 0 62.8% 30.6%;
  --success: 142 76% 26%;
  --warning: 38 92% 40%;
}

body {
  @apply bg-background text-foreground antialiased;
}
```

**Step 6: Delete boilerplate files**

Delete `App.css`, `assets/`, default `App.tsx` content. Replace `App.tsx` with placeholder.

**Step 7: Commit**

```bash
cd C:/Users/bruno/auditor-folha
git add -A && git commit -m "feat: scaffold frontend with Vite + React + Tailwind v4"
```

---

## Task 11: Frontend — API Service + Stores

**Files:**
- Create: `frontend/src/services/api.ts`
- Create: `frontend/src/lib/utils.ts`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/stores/dashboard-store.ts`
- Create: `frontend/src/stores/upload-store.ts`
- Create: `frontend/src/stores/auditoria-store.ts`

**Step 1: Create types**

```ts
// frontend/src/types/index.ts

export interface Contrato {
  id: string;
  codigo: string;
  nome: string;
  cctId: string | null;
  createdAt: string;
  cct?: ConvencaoColetiva | null;
  _count?: { folhas: number };
}

export interface ConvencaoColetiva {
  id: string;
  nome: string;
  sindicato: string;
  vigenciaInicio: string;
  vigenciaFim: string;
  pisos?: PisoCCT[];
}

export interface PisoCCT {
  id: string;
  cargo: string;
  pisoSalarial: string;
  adicionalInsalubridade: string | null;
  adicionalPericulosidade: string | null;
  adicionalNoturno: string | null;
}

export interface FolhaPagamento {
  id: string;
  contratoId: string;
  mesReferencia: string;
  arquivoPdf: string;
  status: 'PENDENTE' | 'PROCESSANDO' | 'CONCLUIDO' | 'ERRO';
  totalProventos: string | null;
  totalDescontos: string | null;
  totalLiquido: string | null;
  erroMsg: string | null;
  processadoEm: string | null;
  createdAt: string;
  contrato?: Contrato;
  funcionarios?: FuncionarioFolha[];
  flags?: AuditFlag[];
  _count?: { funcionarios: number; flags: number };
}

export interface FuncionarioFolha {
  id: string;
  nome: string;
  cpf: string;
  cargo: string;
  salarioBase: string;
  horasExtras50: string;
  horasExtras100: string;
  adicionalNoturno: string;
  adicionalInsalubridade: string;
  adicionalPericulosidade: string;
  faltasDias: number;
  faltasDesconto: string;
  atestadosDias: number;
  dsrDesconto: string;
  valeTransporte: string;
  valeAlimentacao: string;
  inss: string;
  irrf: string;
  outrosProventos: string;
  outrosDescontos: string;
  totalProventos: string;
  totalDescontos: string;
  liquido: string;
  observacoes: string | null;
}

export type Gravidade = 'CRITICO' | 'ALERTA' | 'OPORTUNIDADE';

export interface AuditFlag {
  id: string;
  folhaId: string;
  cpf: string | null;
  regra: string;
  gravidade: Gravidade;
  descricao: string;
  valorAtual: string | null;
  valorCorreto: string | null;
  economiaPotencial: string | null;
  acaoSugerida: string | null;
  createdAt: string;
  folha?: FolhaPagamento;
}

export interface DashboardData {
  totalContratos: number;
  totalFolhas: number;
  flags: { critico: number; alerta: number; oportunidade: number; total: number };
  economiaPotencial: string;
  recentFolhas: FolhaPagamento[];
  topFlags: AuditFlag[];
}

export interface ConfiguracaoAuditoria {
  regra: string;
  ativo: boolean;
  parametros: Record<string, number>;
  parametrosPadrao: Record<string, number>;
}

export const GRAVIDADE_LABELS: Record<Gravidade, string> = {
  CRITICO: 'Critico',
  ALERTA: 'Alerta',
  OPORTUNIDADE: 'Oportunidade',
};

export const GRAVIDADE_COLORS: Record<Gravidade, string> = {
  CRITICO: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
  ALERTA: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200',
  OPORTUNIDADE: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
};
```

**Step 2: Create API service**

```ts
// frontend/src/services/api.ts

class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...opts.headers },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const dashboard = {
  get: () => request<import('@/types').DashboardData>('/dashboard'),
};

export const contratos = {
  list: () => request<import('@/types').Contrato[]>('/contratos'),
  create: (data: { codigo: string; nome: string; cctId?: string }) =>
    request<import('@/types').Contrato>('/contratos', { method: 'POST', body: JSON.stringify(data) }),
};

export const folhas = {
  list: (params?: { contratoId?: string; mesReferencia?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<import('@/types').FolhaPagamento[]>(`/folhas${qs ? `?${qs}` : ''}`);
  },
  get: (id: string) => request<import('@/types').FolhaPagamento>(`/folhas/${id}`),
};

export const upload = {
  send: async (file: File, contratoId: string, mesReferencia: string) => {
    const formData = new FormData();
    formData.append('pdf', file);
    formData.append('contratoId', contratoId);
    formData.append('mesReferencia', mesReferencia);
    const res = await fetch('/api/upload', { method: 'POST', body: formData });
    if (!res.ok) {
      const body = await res.json().catch(() => ({ error: res.statusText }));
      throw new ApiError(res.status, body.error ?? res.statusText);
    }
    return res.json();
  },
};

export const auditoria = {
  flags: (params?: { gravidade?: string; contratoId?: string; mesReferencia?: string; regra?: string }) => {
    const qs = new URLSearchParams(params as Record<string, string>).toString();
    return request<import('@/types').AuditFlag[]>(`/auditoria/flags${qs ? `?${qs}` : ''}`);
  },
  resumo: () => request<any>('/auditoria/resumo'),
};

export const configuracoes = {
  list: () => request<import('@/types').ConfiguracaoAuditoria[]>('/configuracoes'),
  update: (regra: string, data: { ativo?: boolean; parametros?: Record<string, number> }) =>
    request(`/configuracoes/${regra}`, { method: 'PUT', body: JSON.stringify(data) }),
};
```

**Step 3: Create utils**

```ts
// frontend/src/lib/utils.ts
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: string | number | null | undefined): string {
  if (value == null) return 'R$ 0,00';
  const num = typeof value === 'string' ? parseFloat(value) : value;
  return num.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
}

export function formatCPF(cpf: string): string {
  return cpf.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, '$1.$2.$3-$4');
}
```

**Step 4: Commit**

```bash
git add -A && git commit -m "feat: add frontend types, API service, and utils"
```

---

## Task 12: Frontend — App Shell + Router + Layout

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/main.tsx`
- Create: `frontend/src/components/layout/Sidebar.tsx`

**Step 1: Create Sidebar layout**

```tsx
// frontend/src/components/layout/Sidebar.tsx
import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Upload, FileText, ShieldAlert, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/upload', icon: Upload, label: 'Upload' },
  { to: '/auditoria', icon: ShieldAlert, label: 'Auditoria' },
  { to: '/configuracoes', icon: Settings, label: 'Configuracoes' },
];

export function Sidebar() {
  return (
    <aside className="flex h-screen w-64 flex-col border-r border-border bg-card">
      <div className="border-b border-border p-4">
        <h1 className="text-lg font-bold text-foreground">Auditor Folha</h1>
        <p className="text-xs text-muted-foreground">Auditoria de Pagamento</p>
      </div>
      <nav className="flex-1 space-y-1 p-3">
        {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
              isActive
                ? 'bg-primary/10 text-primary font-medium'
                : 'text-muted-foreground hover:bg-muted hover:text-foreground'
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
```

**Step 2: Create App.tsx with router**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import { Sidebar } from '@/components/layout/Sidebar';
import { DashboardPage } from '@/pages/DashboardPage';
import { UploadPage } from '@/pages/UploadPage';
import { FolhaPage } from '@/pages/FolhaPage';
import { AuditoriaPage } from '@/pages/AuditoriaPage';
import { ConfiguracoesPage } from '@/pages/ConfiguracoesPage';

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen">
        <Sidebar />
        <main className="flex-1 overflow-auto bg-background p-6">
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/upload" element={<UploadPage />} />
            <Route path="/folhas/:id" element={<FolhaPage />} />
            <Route path="/auditoria" element={<AuditoriaPage />} />
            <Route path="/configuracoes" element={<ConfiguracoesPage />} />
          </Routes>
        </main>
      </div>
      <Toaster position="top-right" />
    </BrowserRouter>
  );
}
```

**Step 3: Create placeholder pages**

Create empty placeholder components for all 5 pages in `frontend/src/pages/`:
- `DashboardPage.tsx`
- `UploadPage.tsx`
- `FolhaPage.tsx`
- `AuditoriaPage.tsx`
- `ConfiguracoesPage.tsx`

Each one just returns: `<div><h2>Page Name</h2></div>`.

**Step 4: Verify frontend loads**

```bash
cd C:/Users/bruno/auditor-folha/frontend && npm run dev
```

Expected: App loads at `http://localhost:5174` with sidebar and navigation working.

**Step 5: Commit**

```bash
git add -A && git commit -m "feat: add app shell with sidebar and router"
```

---

## Task 13: Frontend — DashboardPage

**Files:**
- Modify: `frontend/src/pages/DashboardPage.tsx`

**Step 1: Implement Dashboard with KPI cards + recent activity**

The page fetches from `/api/dashboard` on mount and displays:
- 4 KPI cards (Contratos, Folhas, Flags, Economia)
- Top 5 critical flags list
- Recent uploads list

Use `useState` + `useEffect` pattern (same as LicitaBrasil's DashboardPage). Use `formatCurrency` for monetary values. Badges use `GRAVIDADE_COLORS` for coloring.

Cards pattern: `rounded-xl border border-border bg-card p-5` with icon from lucide-react.

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: add dashboard page with KPI cards"
```

---

## Task 14: Frontend — UploadPage

**Files:**
- Modify: `frontend/src/pages/UploadPage.tsx`

**Step 1: Implement Upload page**

- Dropzone (using `react-dropzone`) for PDF files
- Select for existing contract or "create new" option
- Input for `mesReferencia` (YYYY-MM format)
- Submit button that calls `upload.send()`
- Progress/loading state during upload
- Success: show summary (X employees, Y flags) with link to folha detail
- Error: show error message

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: add upload page with dropzone"
```

---

## Task 15: Frontend — FolhaPage

**Files:**
- Modify: `frontend/src/pages/FolhaPage.tsx`

**Step 1: Implement Folha detail page**

- Fetches folha by ID from `useParams`
- Shows header with contract name, month, totals
- Table of employees with all fields
- Rows with flags get colored badge
- Columns: Nome, CPF, Cargo, Salario, HE 50%, HE 100%, Adicionais, Faltas, Descontos, Liquido

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: add folha detail page with employee table"
```

---

## Task 16: Frontend — AuditoriaPage

**Files:**
- Modify: `frontend/src/pages/AuditoriaPage.tsx`

**Step 1: Implement Auditoria page**

- Summary bar at top (X criticas, Y alertas, Z oportunidades, economia total)
- Filter selects: gravidade, contrato, mes, regra
- List of flags with:
  - Gravidade badge (colored)
  - Employee name + CPF
  - Rule name + description
  - Valor atual vs. correto
  - Economia potencial
  - Acao sugerida

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: add auditoria page with flags and filters"
```

---

## Task 17: Frontend — ConfiguracoesPage

**Files:**
- Modify: `frontend/src/pages/ConfiguracoesPage.tsx`

**Step 1: Implement Configuracoes page**

- List of all 13 audit rules
- Each rule shows: name, current parameters, toggle on/off
- Edit button opens inline form to adjust parameters
- Save button calls `configuracoes.update()`
- "Restaurar padrao" button per rule

**Step 2: Commit**

```bash
git add -A && git commit -m "feat: add configuracoes page for audit rules"
```

---

## Task 18: End-to-End Verification

**Step 1: Start backend and frontend**

```bash
cd C:/Users/bruno/auditor-folha && npm run dev
```

**Step 2: Create a contract via the API or UI**

```bash
curl -X POST http://localhost:3002/api/contratos -H "Content-Type: application/json" -d '{"codigo":"TEST-001","nome":"Contrato Teste"}'
```

**Step 3: Upload a real PDF via the Upload page**

Navigate to `http://localhost:5174/upload`, select the test contract, set month, upload PDF.

**Step 4: Verify results**

- Dashboard shows updated counts
- Folha detail shows extracted employees
- Auditoria page shows any flags found
- Configuracoes page loads rules

**Step 5: Calibrate PDF parser if needed**

If the parser doesn't extract data correctly from real PDFs, adjust the regex patterns in `pdf-parser.ts` and re-run.

**Step 6: Final commit**

```bash
git add -A && git commit -m "chore: end-to-end verification complete"
```

---

## Summary

| Task | What | Commit |
|------|------|--------|
| 1 | Project scaffolding | `chore: scaffold project structure` |
| 2 | Prisma schema + migration | `feat: add prisma schema` |
| 3 | Backend core (server, config, libs) | `feat: add backend core` |
| 4 | Rubrica mapper + tests | `feat: add rubrica mapper with tests` |
| 5 | PDF parser + tests | `feat: add PDF parser with tests` |
| 6 | Audit engine + tests | `feat: add audit engine with tests` |
| 7 | Routes: contratos + CCT | `feat: add contratos and CCT routes` |
| 8 | Routes: upload + folhas + auditoria | `feat: add upload, folhas, auditoria routes` |
| 9 | Routes: configuracoes + dashboard | `feat: add configuracoes and dashboard routes` |
| 10 | Frontend scaffolding | `feat: scaffold frontend` |
| 11 | API service + types + utils | `feat: add frontend types and API service` |
| 12 | App shell + router + sidebar | `feat: add app shell with router` |
| 13 | DashboardPage | `feat: add dashboard page` |
| 14 | UploadPage | `feat: add upload page` |
| 15 | FolhaPage | `feat: add folha detail page` |
| 16 | AuditoriaPage | `feat: add auditoria page` |
| 17 | ConfiguracoesPage | `feat: add configuracoes page` |
| 18 | E2E verification | `chore: e2e verification` |
