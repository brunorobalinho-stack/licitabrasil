import { Queue } from 'bullmq';
import { redis } from '../lib/redis.js';
import { logger } from '../lib/logger.js';

const connection = redis as any;

export const scrapingQueue = new Queue('scraping', { connection });
export const notificationQueue = new Queue('notifications', { connection });

export async function scheduleScrapingJob(
  sourceName: string,
  params: Record<string, unknown> = {},
): Promise<void> {
  logger.info({ sourceName, params }, 'Scheduling scraping job');
  await scrapingQueue.add(sourceName, { sourceName, params }, {
    removeOnComplete: { count: 100 },
    removeOnFail: { count: 50 },
    attempts: 3,
    backoff: { type: 'exponential', delay: 5000 },
  });
}

export async function scheduleNotificationJob(
  alertaId: string,
  licitacaoIds: string[],
): Promise<void> {
  await notificationQueue.add('send-alert', { alertaId, licitacaoIds }, {
    removeOnComplete: { count: 200 },
    removeOnFail: { count: 50 },
    attempts: 2,
    backoff: { type: 'fixed', delay: 10000 },
  });
}
