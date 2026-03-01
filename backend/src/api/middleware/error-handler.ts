import { Request, Response, NextFunction } from 'express';
import { logger } from '../../lib/logger.js';
import { ZodError } from 'zod';

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
    res.status(400).json({ error: 'Dados inválidos', details: err.errors });
    return;
  }
  res.status(500).json({ error: 'Erro interno do servidor' });
};
