import { Router, Request, Response, NextFunction } from 'express';
import crypto from 'node:crypto';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { prisma } from '../../lib/prisma.js';
import { env } from '../../config/env.js';
import { authMiddleware, AuthPayload } from '../middleware/auth.js';
import { AppError } from '../middleware/error-handler.js';
import { sendPasswordResetEmail } from '../../lib/email.js';

const router = Router();

// ---------------------------------------------------------------------------
// Validation schemas
// ---------------------------------------------------------------------------

const registerSchema = z.object({
  email: z.string().email('Email inválido'),
  nome: z.string().min(2, 'Nome deve ter pelo menos 2 caracteres'),
  senha: z.string().min(8, 'Senha deve ter pelo menos 8 caracteres'),
  empresa: z.string().optional(),
  cnpj: z.string().optional(),
});

const loginSchema = z.object({
  email: z.string().email('Email inválido'),
  senha: z.string().min(1, 'Senha é obrigatória'),
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
// Helper: generate JWT pair + cookie helpers
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

const isProduction = env.NODE_ENV === 'production';

function setAuthCookies(res: Response, tokens: { accessToken: string; refreshToken: string }) {
  res.cookie('accessToken', tokens.accessToken, {
    httpOnly: true,
    secure: isProduction,
    sameSite: 'lax',
    maxAge: 15 * 60 * 1000,
  });
  res.cookie('refreshToken', tokens.refreshToken, {
    httpOnly: true,
    secure: isProduction,
    sameSite: 'lax',
    path: '/api/auth/refresh',
    maxAge: 7 * 24 * 60 * 60 * 1000,
  });
}

function clearAuthCookies(res: Response) {
  res.clearCookie('accessToken');
  res.clearCookie('refreshToken', { path: '/api/auth/refresh' });
}

// ---------------------------------------------------------------------------
// POST /register
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/register:
 *   post:
 *     tags: [Auth]
 *     summary: Cadastrar novo usuário
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/RegisterRequest'
 *     responses:
 *       201:
 *         description: Usuário criado (cookies HttpOnly setados)
 *       409:
 *         description: Email já cadastrado
 */
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

  const tokens = generateTokens({ userId: user.id, email: user.email, role: user.role });
  setAuthCookies(res, tokens);

  res.status(201).json({
    user: { id: user.id, email: user.email, nome: user.nome, empresa: user.empresa, cnpj: user.cnpj, role: user.role },
  });
}));

// ---------------------------------------------------------------------------
// POST /login
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/login:
 *   post:
 *     tags: [Auth]
 *     summary: Login
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             $ref: '#/components/schemas/LoginRequest'
 *     responses:
 *       200:
 *         description: Login bem-sucedido (cookies HttpOnly setados)
 *       401:
 *         description: Credenciais inválidas
 */
router.post('/login', asyncHandler(async (req, res) => {
  const data = loginSchema.parse(req.body);

  const user = await prisma.usuario.findUnique({ where: { email: data.email } });
  if (!user) throw new AppError(401, 'Credenciais inválidas');

  const valid = await bcrypt.compare(data.senha, user.senha);
  if (!valid) throw new AppError(401, 'Credenciais inválidas');

  const tokens = generateTokens({ userId: user.id, email: user.email, role: user.role });
  setAuthCookies(res, tokens);

  res.json({
    user: { id: user.id, email: user.email, nome: user.nome, empresa: user.empresa, cnpj: user.cnpj, role: user.role },
  });
}));

// ---------------------------------------------------------------------------
// POST /refresh
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/refresh:
 *   post:
 *     tags: [Auth]
 *     summary: Renovar access token via refresh cookie
 *     responses:
 *       200:
 *         description: Token atualizado
 *       401:
 *         description: Refresh token inválido
 */
router.post('/refresh', asyncHandler(async (req, res) => {
  const refreshToken = req.cookies?.refreshToken;
  if (!refreshToken) throw new AppError(401, 'Refresh token não fornecido');

  try {
    const decoded = jwt.verify(refreshToken, env.JWT_REFRESH_SECRET) as AuthPayload;
    const tokens = generateTokens({ userId: decoded.userId, email: decoded.email, role: decoded.role || 'USER' });
    setAuthCookies(res, tokens);
    res.json({ message: 'Token atualizado' });
  } catch {
    throw new AppError(401, 'Refresh token inválido ou expirado');
  }
}));

// ---------------------------------------------------------------------------
// POST /logout
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/logout:
 *   post:
 *     tags: [Auth]
 *     summary: Logout (limpa cookies)
 *     responses:
 *       200:
 *         description: Logout realizado
 */
router.post('/logout', (_req, res) => {
  clearAuthCookies(res);
  res.json({ message: 'Logout realizado' });
});

// ---------------------------------------------------------------------------
// POST /forgot-password
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/forgot-password:
 *   post:
 *     tags: [Auth]
 *     summary: Solicitar redefinição de senha
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [email]
 *             properties:
 *               email:
 *                 type: string
 *                 format: email
 *     responses:
 *       200:
 *         description: Sempre retorna 200 (prevenção de enumeração)
 */
router.post('/forgot-password', asyncHandler(async (req, res) => {
  const { email } = z.object({ email: z.string().email() }).parse(req.body);

  // Always return 200 to prevent user enumeration
  const user = await prisma.usuario.findUnique({ where: { email } });
  if (user) {
    const rawToken = crypto.randomUUID();
    const hashedToken = crypto.createHash('sha256').update(rawToken).digest('hex');

    await prisma.usuario.update({
      where: { id: user.id },
      data: {
        resetToken: hashedToken,
        resetTokenExpiry: new Date(Date.now() + 60 * 60 * 1000), // 1 hour
      },
    });

    await sendPasswordResetEmail(email, rawToken);
  }

  res.json({ message: 'Se o email existir, você receberá um link de redefinição.' });
}));

// ---------------------------------------------------------------------------
// POST /reset-password
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/reset-password:
 *   post:
 *     tags: [Auth]
 *     summary: Redefinir senha com token
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema:
 *             type: object
 *             required: [token, senha]
 *             properties:
 *               token:
 *                 type: string
 *               senha:
 *                 type: string
 *                 minLength: 8
 *     responses:
 *       200:
 *         description: Senha redefinida
 *       400:
 *         description: Token inválido ou expirado
 */
router.post('/reset-password', asyncHandler(async (req, res) => {
  const { token, senha } = z.object({
    token: z.string().min(1),
    senha: z.string().min(8, 'Senha deve ter pelo menos 8 caracteres'),
  }).parse(req.body);

  const hashedToken = crypto.createHash('sha256').update(token).digest('hex');

  const user = await prisma.usuario.findFirst({
    where: {
      resetToken: hashedToken,
      resetTokenExpiry: { gt: new Date() },
    },
  });

  if (!user) throw new AppError(400, 'Token inválido ou expirado');

  const hashedPassword = await bcrypt.hash(senha, 10);

  await prisma.usuario.update({
    where: { id: user.id },
    data: {
      senha: hashedPassword,
      resetToken: null,
      resetTokenExpiry: null,
    },
  });

  res.json({ message: 'Senha redefinida com sucesso' });
}));

// ---------------------------------------------------------------------------
// GET /me
// ---------------------------------------------------------------------------
/** @openapi
 * /auth/me:
 *   get:
 *     tags: [Auth]
 *     summary: Dados do usuário autenticado
 *     security:
 *       - cookieAuth: []
 *     responses:
 *       200:
 *         description: Dados do usuário
 *         content:
 *           application/json:
 *             schema:
 *               $ref: '#/components/schemas/Usuario'
 *       401:
 *         description: Não autenticado
 */
router.get('/me', authMiddleware, asyncHandler(async (req, res) => {
  const user = await prisma.usuario.findUnique({
    where: { id: req.user!.userId },
    select: {
      id: true,
      email: true,
      nome: true,
      empresa: true,
      cnpj: true,
      role: true,
      criadoEm: true,
      atualizadoEm: true,
    },
  });

  if (!user) throw new AppError(404, 'Usuário não encontrado');
  res.json(user);
}));

export { router as authRouter };
