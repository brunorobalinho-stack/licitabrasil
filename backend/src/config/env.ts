import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const SECRET_HINT = 'Generate with: openssl rand -base64 48';

const envSchema = z.object({
  DATABASE_URL: z.string(),
  REDIS_URL: z.string().default('redis://localhost:6379'),
  JWT_SECRET: z.string().min(32, `JWT_SECRET must be at least 32 characters. ${SECRET_HINT}`),
  JWT_REFRESH_SECRET: z.string().min(32, `JWT_REFRESH_SECRET must be at least 32 characters. ${SECRET_HINT}`),
  JWT_EXPIRES_IN: z.string().default('15m'),
  JWT_REFRESH_EXPIRES_IN: z.string().default('7d'),
  PORT: z.coerce.number().default(3001),
  NODE_ENV: z.enum(['development', 'production', 'test']).default('development'),
  CORS_ORIGIN: z.string().default('http://localhost:5173'),
  PNCP_API_BASE: z.string().default('https://pncp.gov.br/api/consulta'),
  QUERIDO_DIARIO_API_BASE: z.string().default('https://queridodiario.ok.org.br/api'),
  SCRAPING_CONCURRENCY: z.coerce.number().default(3),
  SCRAPING_RATE_LIMIT_MS: z.coerce.number().default(1000),
  LOG_LEVEL: z.string().default('info'),
});

// Refuse to boot if JWT secrets match any value that has historically
// shipped in this repo (docker-compose.yml or .env.example). Adding to
// this set is cheap; please do not weaken it.
const LEGACY_SECRETS = new Set([
  'your-super-secret-jwt-key-change-in-production',
  'your-super-secret-refresh-key-change-in-production',
  'licitabrasil-jwt-secret-change-in-production',
  'licitabrasil-refresh-secret-change-in-production',
]);

const parsed = envSchema.parse(process.env);

if (LEGACY_SECRETS.has(parsed.JWT_SECRET) || LEGACY_SECRETS.has(parsed.JWT_REFRESH_SECRET)) {
  throw new Error(
    'Refusing to start: JWT_SECRET or JWT_REFRESH_SECRET is set to a known default value. ' +
    SECRET_HINT,
  );
}

export const env = parsed;
export type Env = z.infer<typeof envSchema>;
