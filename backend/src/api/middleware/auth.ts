import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { env } from '../../config/env.js';

// Source of truth for what a valid JWT body looks like. Zod-checked at
// every middleware call so a malformed token can never reach a route
// handler with `req.user.userId === undefined`.
const authPayloadSchema = z.object({
  userId: z.string().min(1),
  email: z.string().email(),
});

export type AuthPayload = z.infer<typeof authPayloadSchema>;

declare global {
  namespace Express {
    interface Request {
      user?: AuthPayload;
    }
  }
}

function parseAuthHeader(req: Request): string | null {
  const header = req.headers.authorization;
  if (!header) return null;
  if (!header.startsWith('Bearer ')) return null;
  return header.slice('Bearer '.length).trim() || null;
}

export const authMiddleware = (req: Request, res: Response, next: NextFunction): void => {
  const token = parseAuthHeader(req);
  if (!token) {
    res.status(401).json({ error: 'Token não fornecido' });
    return;
  }
  try {
    const decoded = jwt.verify(token, env.JWT_SECRET);
    req.user = authPayloadSchema.parse(decoded);
    next();
  } catch {
    res.status(401).json({ error: 'Token inválido ou expirado' });
  }
};

export const optionalAuth = (req: Request, _res: Response, next: NextFunction): void => {
  const token = parseAuthHeader(req);
  if (token) {
    try {
      const decoded = jwt.verify(token, env.JWT_SECRET);
      req.user = authPayloadSchema.parse(decoded);
    } catch {
      /* ignore invalid or malformed tokens */
    }
  }
  next();
};
