import dotenv from 'dotenv';
import { z } from 'zod';

dotenv.config();

const envSchema = z.object({
  DATABASE_URL: z.string(),
  REDIS_URL: z.string().default('redis://localhost:6379'),
  JWT_SECRET: z.string(),
  JWT_REFRESH_SECRET: z.string(),
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

export const env = envSchema.parse(process.env);
export type Env = z.infer<typeof envSchema>;
