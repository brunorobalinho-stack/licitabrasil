import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { env } from '../../config/env.js';

export interface AuthPayload {
  userId: string;
  email: string;
}

declare global {
  namespace Express {
    interface Request {
      user?: AuthPayload;
    }
  }
}

export const authMiddleware = (req: Request, res: Response, next: NextFunction): void => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) {
    res.status(401).json({ error: 'Token não fornecido' });
    return;
  }
  try {
    const decoded = jwt.verify(token, env.JWT_SECRET) as AuthPayload;
    req.user = decoded;
    next();
  } catch {
    res.status(401).json({ error: 'Token inválido ou expirado' });
  }
};

export const optionalAuth = (req: Request, _res: Response, next: NextFunction): void => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (token) {
    try {
      req.user = jwt.verify(token, env.JWT_SECRET) as AuthPayload;
    } catch {
      /* ignore invalid tokens */
    }
  }
  next();
};
