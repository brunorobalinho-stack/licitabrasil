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

const registerSchema = z.object({
  email: z.string().email('Email inválido'),
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  senha: z.string().min(6, 'Senha deve ter pelo menos 6 caracteres'),
  empresa: z.string().optional(),
  cnpj: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  senha: z.string().min(1, 'Senha é obrigatória'),
});

const refreshSchema = z.object({
  refreshToken: z.string().min(1, 'Refresh token é obrigatório'),
});

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

  res.status(201).json({
    user: { id: user.id, email: user.email, nome: user.nome, empresa: user.empresa, cnpj: user.cnpj },
    ...tokens,
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

  res.json({
    user: { id: user.id, email: user.email, nome: user.nome, empresa: user.empresa, cnpj: user.cnpj },
    ...tokens,
  });
}));

// ---------------------------------------------------------------------------
// POST /refresh
// ---------------------------------------------------------------------------

router.post('/refresh', asyncHandler(async (req, res) => {
  const { refreshToken } = refreshSchema.parse(req.body);

  try {
    const decoded = jwt.verify(refreshToken, env.JWT_REFRESH_SECRET) as AuthPayload;
    const tokens = generateTokens({ userId: decoded.userId, email: decoded.email });
    res.json(tokens);
  } catch {
    throw new AppError(401, 'Refresh token inválido ou expirado');
  }
}));

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
