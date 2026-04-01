import { Resend } from 'resend';
import { env } from '../config/env.js';
import { logger } from './logger.js';

const resend = env.RESEND_API_KEY ? new Resend(env.RESEND_API_KEY) : null;

const FROM = 'LicitaBrasil <noreply@licitabrasil.com.br>';

export async function sendPasswordResetEmail(to: string, token: string): Promise<boolean> {
  const resetUrl = `${env.APP_URL}/redefinir-senha?token=${token}`;

  if (!resend) {
    logger.warn({ to, resetUrl }, 'RESEND_API_KEY not set — email not sent (logged for dev)');
    return true; // dev mode: pretend success
  }

  try {
    await resend.emails.send({
      from: FROM,
      to,
      subject: 'Redefinição de senha — LicitaBrasil',
      html: `
        <h2>Redefinição de senha</h2>
        <p>Você solicitou a redefinição da sua senha.</p>
        <p>Clique no link abaixo para criar uma nova senha:</p>
        <p><a href="${resetUrl}" style="background:#2563eb;color:#fff;padding:10px 20px;border-radius:6px;text-decoration:none;display:inline-block">Redefinir senha</a></p>
        <p>Este link expira em 1 hora.</p>
        <p>Se você não fez essa solicitação, ignore este email.</p>
        <hr>
        <p style="color:#888;font-size:12px">LicitaBrasil — Pesquisa unificada de licitações públicas</p>
      `,
    });
    return true;
  } catch (err) {
    logger.error({ err, to }, 'Failed to send password reset email');
    return false;
  }
}

export async function sendAlertEmail(
  to: string,
  alertaNome: string,
  licitacoes: Array<{ id: string; objeto: string; orgao: string; valorEstimado?: string }>,
): Promise<boolean> {
  if (!resend) {
    logger.warn({ to, alertaNome, count: licitacoes.length }, 'RESEND_API_KEY not set — alert email not sent');
    return true;
  }

  const items = licitacoes.map(l =>
    `<li><a href="${env.APP_URL}/licitacao/${l.id}">${l.objeto}</a> — ${l.orgao}${l.valorEstimado ? ` (R$ ${l.valorEstimado})` : ''}</li>`
  ).join('');

  try {
    await resend.emails.send({
      from: FROM,
      to,
      subject: `Novas licitações encontradas — ${alertaNome}`,
      html: `
        <h2>Alerta: ${alertaNome}</h2>
        <p>Encontramos ${licitacoes.length} nova(s) licitação(ões) para seu alerta:</p>
        <ul>${items}</ul>
        <hr>
        <p style="color:#888;font-size:12px">LicitaBrasil — Pesquisa unificada de licitações públicas</p>
      `,
    });
    return true;
  } catch (err) {
    logger.error({ err, to, alertaNome }, 'Failed to send alert email');
    return false;
  }
}
