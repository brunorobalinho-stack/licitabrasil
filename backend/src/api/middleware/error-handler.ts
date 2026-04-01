import { Request, Response, NextFunction } from 'express';
import { logger } from '../../lib/logger.js';
import { ZodError } from 'zod';
import { env } from '../../config/env.js';

export class AppError extends Error {
  constructor(public statusCode: number, message: string) {
    super(message);
    this.name = 'AppError';
  }
}

export const errorHandler = (err: Error, _req: Request, res: Response, _next: NextFunction): void => {
  logger.error({ err }, 'Unhandled error');

  if (err instanceof AppError) {
    res.status(err.statusCode).json({ error: err.message });
    return;
  }
  if (err instanceof ZodError) {
    // Em produção, expor apenas campo + mensagem (sem code/expected/received)
    const details = env.NODE_ENV === 'production'
      ? err.errors.map(e => ({ path: e.path, message: e.message }))
      : err.errors;
    res.status(400).json({ error: 'Dados inválidos', details });
    return;
  }
  res.status(500).json({ error: 'Erro interno do servidor' });
};
