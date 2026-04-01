import { Worker, Job } from 'bullmq';
import { redis } from '../lib/redis.js';
import { logger } from '../lib/logger.js';
import { prisma } from '../lib/prisma.js';
import { sendAlertEmail } from '../lib/email.js';

interface NotificationJobData {
  alertaId: string;
  licitacaoIds: string[];
}

const notificationWorker = new Worker(
  'notifications',
  async (job: Job<NotificationJobData>) => {
    const { alertaId, licitacaoIds } = job.data;
    const log = logger.child({ jobId: job.id, alertaId });

    const alerta = await prisma.alerta.findUnique({
      where: { id: alertaId },
      include: { usuario: { select: { email: true, nome: true } } },
    });

    if (!alerta || !alerta.ativo) {
      log.warn('Alerta not found or inactive, skipping');
      return { skipped: true };
    }

    const licitacoes = await prisma.licitacao.findMany({
      where: { id: { in: licitacaoIds } },
      select: { id: true, objeto: true, orgao: true, valorEstimado: true },
    });

    if (licitacoes.length === 0) {
      log.warn('No matching licitacoes found');
      return { sent: 0 };
    }

    // Send email
    const alertaNome = alerta.palavrasChave.join(', ');
    await sendAlertEmail(
      alerta.usuario.email,
      alertaNome,
      licitacoes.map(l => ({
        id: l.id,
        objeto: l.objeto,
        orgao: l.orgao,
        valorEstimado: l.valorEstimado?.toString(),
      })),
    );

    // Record matches and update alerta stats
    const matchData = licitacaoIds.map(licitacaoId => ({
      alertaId,
      licitacaoId,
    }));

    await prisma.$transaction([
      prisma.alertaMatch.createMany({ data: matchData, skipDuplicates: true }),
      prisma.alerta.update({
        where: { id: alertaId },
        data: {
          ultimoEnvio: new Date(),
          totalEnviados: { increment: licitacoes.length },
        },
      }),
    ]);

    log.info({ sent: licitacoes.length }, 'Alert notification sent');
    return { sent: licitacoes.length };
  },
  {
    connection: redis as any,
    concurrency: 5,
  },
);

notificationWorker.on('completed', (job, result) => {
  logger.info({ jobId: job?.id, result }, 'Notification job completed');
});

notificationWorker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err: err.message }, 'Notification job failed');
});

export { notificationWorker };
