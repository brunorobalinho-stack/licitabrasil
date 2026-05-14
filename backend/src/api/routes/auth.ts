import { Router, Request, Response, NextFunction } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { prisma } from '../../lib/prisma.js';
import { env } from '../../config/env.js';
import { authMiddleware, AuthPayload } from '../middleware/auth.js';
import { AppError } from '../middleware/error-handler.js';

const router = Router();

// ---------------------------------------------------------------------------
// Validation schemas
// ---------------------------------------------------------------------------

// Normalize email: trim whitespace, lowercase. Storing lowercase makes
// `findUnique({ where: { email } })` reliable across capitalization.
const emailField = z
  .string()
  .email('Email inválido')
  .transform((s) => s.trim().toLowerCase());

const registerSchema = z.object({
  email: emailField,
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  senha: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres'),
  empresa: z.string().optional(),
  cnpj: z.string().optional(),
});

const loginSchema = z.object({
  email: emailField,
  senha: z.string().min(1, 'Senha é obrigatória'),
});

// ---------------------------------------------------------------------------
// Refresh token cookie
// ---------------------------------------------------------------------------

const REFRESH_COOKIE = 'refreshToken';

// Flags do cookie do refresh token. httpOnly tira o token do alcance do
// JS do navegador (logo, de XSS); path restrito a /api/auth pra ele nao
// ser enviado pro resto da API; sameSite strict porque o /refresh so e
// chamado pelo proprio app. set e clear compartilham essa base pra nao
// driftarem -- se as flags divergirem, o browser ignora o clearCookie.
const refreshCookieBase = {
  httpOnly: true,
  secure: env.NODE_ENV === 'production',
  sameSite: 'strict' as const,
  path: '/api/auth',
};

function setRefreshCookie(res: Response, token: string): void {
  res.cookie(REFRESH_COOKIE, token, {
    ...refreshCookieBase,
    maxAge: 7 * 24 * 60 * 60 * 1000, // 7d, casado com JWT_REFRESH_EXPIRES_IN
  });
}

function clearRefreshCookie(res: Response): void {
  res.clearCookie(REFRESH_COOKIE, refreshCookieBase);
}

// ---------------------------------------------------------------------------
// Helper: wrap async route handlers
// ---------------------------------------------------------------------------

type AsyncHandler = (req: Request, res: Response, next: NextFunction) => Promise<void>;

function asyncHandler(fn: AsyncHandler) {
  return (req: Request, res: Response, next: NextFunction) => {
    fn(req, res, next).catch(next);
  };
}

// ---------------------------------------------------------------------------
// Helper: generate JWT pair
// ---------------------------------------------------------------------------

function generateTokens(payload: AuthPayload) {
  const accessToken = jwt.sign(payload, env.JWT_SECRET, {
    expiresIn: env.JWT_EXPIRES_IN,
  } as jwt.SignOptions);
  const refreshToken = jwt.sign(payload, env.JWT_REFRESH_SECRET, {
    expiresIn: env.JWT_REFRESH_EXPIRES_IN,
  } as jwt.SignOptions);
  return { accessToken, refreshToken };
}

// ---------------------------------------------------------------------------
// POST /register
// ---------------------------------------------------------------------------

router.post('/register', asyncHandler(async (req, res) => {
  const data = registerSchema.parse(req.body);

  const existing = await prisma.usuario.findUnique({ where: { email: data.email } });
  if (existing) throw new AppError(409, 'Email já cadastrado');

  const hashedPassword = await bcrypt.hash(data.senha, 10);

  const user = await prisma.usuario.create({
    data: {
      email: data.email,
      nome: data.nome,
      senha: hashedPassword,
      empresa: data.empresa,
      cnpj: data.cnpj,
    },
  });

  const tokens = generateTokens({ userId: user.id, email: user.email });
  // Refresh token vai em cookie httpOnly; so o access token (curto, 15min)
  // volta no corpo pro client guardar e mandar no header Authorization.
  setRefreshCookie(res, tokens.refreshToken);

  res.status(201).json({
    user: { id: user.id, email: user.email, nome: user.nome, empresa: user.empresa, cnpj: user.cnpj },
    accessToken: tokens.accessToken,
  });
}));

// ---------------------------------------------------------------------------
// POST /login
// ---------------------------------------------------------------------------

router.post('/login', asyncHandler(async (req, res) => {
  const data = loginSchema.parse(req.body);

  const user = await prisma.usuario.findUnique({ where: { email: data.email } });
  if (!user) throw new AppError(401, 'Credenciais inválidas');

  const valid = await bcrypt.compare(data.senha, user.senha);
  if (!valid) throw new AppError(401, 'Credenciais inválidas');

  const tokens = generateTokens({ userId: user.id, email: user.email });
  setRefreshCookie(res, tokens.refreshToken);

  res.json({
    user: { id: user.id, email: user.email, nome: user.nome, empresa: user.empresa, cnpj: user.cnpj },
    accessToken: tokens.accessToken,
  });
}));

// ---------------------------------------------------------------------------
// POST /refresh
// ---------------------------------------------------------------------------

router.post('/refresh', asyncHandler(async (req, res) => {
  const refreshToken = req.cookies?.[REFRESH_COOKIE];
  if (!refreshToken) throw new AppError(401, 'Refresh token não encontrado');

  let decoded: AuthPayload;
  try {
    decoded = jwt.verify(refreshToken, env.JWT_REFRESH_SECRET) as AuthPayload;
  } catch {
    // Token invalido/expirado: limpa o cookie morto pra os proximos
    // /refresh pararem direto no `if (!refreshToken)` acima.
    clearRefreshCookie(res);
    throw new AppError(401, 'Refresh token inválido ou expirado');
  }

  // Autoridade: o refresh token e a credencial de 7 dias. Confirma que a
  // conta ainda existe antes de re-emitir -- senao um usuario deletado
  // renovaria o acesso pela semana inteira.
  const user = await prisma.usuario.findUnique({
    where: { id: decoded.userId },
    select: { id: true, email: true },
  });
  if (!user) {
    clearRefreshCookie(res);
    throw new AppError(401, 'Conta não encontrada');
  }

  // Rotaciona: cada /refresh emite um par novo, inclusive o refresh.
  const tokens = generateTokens({ userId: user.id, email: user.email });
  setRefreshCookie(res, tokens.refreshToken);
  res.json({ accessToken: tokens.accessToken });
}));

// ---------------------------------------------------------------------------
// POST /logout
// ---------------------------------------------------------------------------

router.post('/logout', (_req, res) => {
  clearRefreshCookie(res);
  res.status(204).end();
});

// ---------------------------------------------------------------------------
// GET /me
// ---------------------------------------------------------------------------

router.get('/me', authMiddleware, asyncHandler(async (req, res) => {
  const user = await prisma.usuario.findUnique({
    where: { id: req.user!.userId },
    select: {
      id: true,
      email: true,
      nome: true,
      empresa: true,
      cnpj: true,
      criadoEm: true,
      atualizadoEm: true,
    },
  });

  if (!user) throw new AppError(404, 'Usuário não encontrado');
  res.json(user);
}));

export { router as authRouter };
