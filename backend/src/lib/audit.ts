import type { PrismaClient } from '@prisma/client';
import { logger } from './logger.js';

const AUDITED_MODELS = new Set([
  'Licitacao', 'Usuario', 'Alerta', 'Favorito', 'BuscaSalva', 'FonteDados',
]);

function lowerFirst(s: string): string {
  return s.charAt(0).toLowerCase() + s.slice(1);
}

function safeJson(val: unknown): any {
  try { return JSON.parse(JSON.stringify(val)); } catch { return null; }
}

/**
 * Build query extension config for Prisma.$extends().
 * `base` is the raw PrismaClient used to INSERT audit rows
 * (avoids recursion since AuditLog writes go through the unextended client).
 */
export function auditExtension(base: PrismaClient) {
  const write = (action: string, model: string, recordId: string, oldValue?: unknown, newValue?: unknown) => {
    base.auditLog.create({
      data: {
        action,
        model,
        recordId,
        oldValue: oldValue ? safeJson(oldValue) : undefined,
        newValue: newValue ? safeJson(newValue) : undefined,
      },
    }).catch((err) => logger.warn({ err, model, action }, 'Audit log write failed'));
  };

  return {
    query: {
      $allModels: {
        async create({ model, args, query }: any) {
          const result = await query(args);
          if (AUDITED_MODELS.has(model)) {
            write('CREATE', model, String(result?.id ?? 'unknown'), undefined, result);
          }
          return result;
        },

        async update({ model, args, query }: any) {
          let oldValue: unknown = null;
          if (AUDITED_MODELS.has(model) && args?.where) {
            try { oldValue = await (base as any)[lowerFirst(model)].findUnique({ where: args.where }); } catch {}
          }
          const result = await query(args);
          if (AUDITED_MODELS.has(model)) {
            write('UPDATE', model, String(result?.id ?? args?.where?.id ?? 'unknown'), oldValue, result);
          }
          return result;
        },

        async delete({ model, args, query }: any) {
          let oldValue: unknown = null;
          if (AUDITED_MODELS.has(model) && args?.where) {
            try { oldValue = await (base as any)[lowerFirst(model)].findUnique({ where: args.where }); } catch {}
          }
          const result = await query(args);
          if (AUDITED_MODELS.has(model)) {
            write('DELETE', model, String(result?.id ?? args?.where?.id ?? 'unknown'), oldValue, undefined);
          }
          return result;
        },

        async upsert({ model, args, query }: any) {
          const result = await query(args);
          if (AUDITED_MODELS.has(model)) {
            write('UPSERT', model, String(result?.id ?? 'unknown'), undefined, result);
          }
          return result;
        },
      },
    },
  };
}
