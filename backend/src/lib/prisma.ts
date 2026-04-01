import { PrismaClient } from '@prisma/client';
import { env } from '../config/env.js';
import { logger } from './logger.js';
import { auditExtension } from './audit.js';

const globalForPrisma = globalThis as unknown as { prisma: ReturnType<typeof createPrisma> };

function createPrisma() {
  const base = new PrismaClient({
    log: env.NODE_ENV === 'development'
      ? [
          { emit: 'event', level: 'query' },
          { emit: 'stdout', level: 'error' },
          { emit: 'stdout', level: 'warn' },
        ]
      : [{ emit: 'stdout', level: 'error' }],
  });

  // Slow query logging (development only)
  if (env.NODE_ENV === 'development') {
    (base as any).$on('query', (e: { duration: number; query: string }) => {
      if (e.duration > 200) {
        logger.warn(
          { duration: `${e.duration}ms`, query: e.query.slice(0, 300) },
          'Slow query detected',
        );
      }
    });
  }

  // Set statement timeout (30s) to prevent runaway queries
  base.$executeRawUnsafe('SET statement_timeout = 30000').catch(() => {});

  // Apply audit logging extension (writes go through `base` to avoid recursion)
  return base.$extends(auditExtension(base));
}

export const prisma = globalForPrisma.prisma ?? createPrisma();

if (env.NODE_ENV !== 'production') globalForPrisma.prisma = prisma;
