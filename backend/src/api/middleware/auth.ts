import { Request, Response, NextFunction } from 'express';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { env } from '../../config/env.js';
import { prisma } from '../../lib/prisma.js';

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

/**
 * Confirma que o `userId` do token corresponde a uma conta que ainda
 * existe. O Zod valida o SHAPE do payload, mas um token bem-formado e
 * assinado pode pertencer a uma conta ja deletada -- e seguiria valendo
 * ate expirar (e o /refresh re-emitiria por 7 dias). A checagem no banco
 * a cada request da revogacao imediata, ao custo de um round-trip.
 */
async function userExists(userId: string): Promise<boolean> {
  const user = await prisma.usuario.findUnique({
    where: { id: userId },
    select: { id: true },
  });
  return user !== null;
}

export const authMiddleware = async (
  req: Request,
  res: Response,
  next: NextFunction,
): Promise<void> => {
  const token = parseAuthHeader(req);
  if (!token) {
    res.status(401).json({ error: 'Token não fornecido' });
    return;
  }

  let payload: AuthPayload;
  try {
    payload = authPayloadSchema.parse(jwt.verify(token, env.JWT_SECRET));
  } catch {
    res.status(401).json({ error: 'Token inválido ou expirado' });
    return;
  }

  try {
    if (!(await userExists(payload.userId))) {
      res.status(401).json({ error: 'Conta não encontrada' });
      return;
    }
  } catch (err) {
    // Falha no banco nao e culpa do token: deixa o errorHandler decidir o
    // status em vez de mascarar uma indisponibilidade como 401.
    next(err);
    return;
  }

  req.user = payload;
  next();
};

export const optionalAuth = async (
  req: Request,
  _res: Response,
  next: NextFunction,
): Promise<void> => {
  const token = parseAuthHeader(req);
  if (token) {
    try {
      const payload = authPayloadSchema.parse(jwt.verify(token, env.JWT_SECRET));
      // Auth e opcional aqui: se o banco tropecar, segue como anonimo em
      // vez de derrubar a request.
      if (await userExists(payload.userId)) {
        req.user = payload;
      }
    } catch {
      /* ignora token invalido/malformado e falhas de banco */
    }
  }
  next();
};
