import cron from 'node-cron';
import { scheduleScrapingJob } from '../jobs/queues.js';
import { matchAlerts } from '../jobs/alert-matcher.js';
import { prisma } from '../lib/prisma.js';
import { logger } from '../lib/logger.js';

export function startScheduler(): void {
  // PNCP — every 30 minutes (API allows pageSize 10-50)
  cron.schedule('*/30 * * * *', async () => {
    logger.info('Cron: scheduling PNCP scraping');
    await scheduleScrapingJob('pncp', { pageSize: 50 });
  });

  // Querido Diário — every 6 hours
  cron.schedule('0 */6 * * *', async () => {
    logger.info('Cron: scheduling Querido Diário scraping');
    await scheduleScrapingJob('querido-diario', { size: 50 });
  });

  // ConLicitação — every 2 hours
  cron.schedule('0 */2 * * *', async () => {
    logger.info('Cron: scheduling ConLicitação scraping');
    await scheduleScrapingJob('conlicitacao', { pageSize: 50 });
  });

  // ComprasNet (via PNCP) — every hour
  cron.schedule('30 * * * *', async () => {
    logger.info('Cron: scheduling ComprasNet scraping');
    await scheduleScrapingJob('comprasnet', { pageSize: 50 });
  });

  // DOU (Diário Oficial) — every 2 hours, Seção 3
  cron.schedule('15 */2 * * *', async () => {
    logger.info('Cron: scheduling DOU scraping');
    await scheduleScrapingJob('dou', { pageSize: 20 });
  });

  // BEC SP — every 2 hours
  cron.schedule('45 */2 * * *', async () => {
    logger.info('Cron: scheduling BEC SP scraping');
    await scheduleScrapingJob('bec-sp', {});
  });

  // Licitações-e — every hour
  cron.schedule('0 * * * *', async () => {
    logger.info('Cron: scheduling Licitações-e scraping');
    await scheduleScrapingJob('licitacoes-e', {});
  });

  // ComprasNet ARP — every 6 hours
  cron.schedule('0 1,7,13,19 * * *', async () => {
    logger.info('Cron: scheduling ComprasNet ARP scraping');
    await scheduleScrapingJob('comprasnet-arp', {});
  });

  // ComprasNet Contratos — every 4 hours
  cron.schedule('30 */4 * * *', async () => {
    logger.info('Cron: scheduling ComprasNet Contratos scraping');
    await scheduleScrapingJob('comprasnet-contratos', {});
  });

  // Run initial scraping 30 s after startup
  setTimeout(async () => {
    logger.info('Running initial scraping jobs…');
    await scheduleScrapingJob('pncp', { pageSize: 50 });
  }, 30_000);

  // DIARIO alert digest — every day at 8:00 AM
  cron.schedule('0 8 * * *', async () => {
    logger.info('Cron: running daily alert matcher');
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    const recent = await prisma.licitacao.findMany({
      where: { criadoEm: { gte: yesterday } },
      select: { id: true },
    });
    if (recent.length > 0) {
      await matchAlerts(recent.map(l => l.id), ['DIARIO']);
    }
  });

  // SEMANAL alert digest — every Monday at 8:00 AM
  cron.schedule('0 8 * * 1', async () => {
    logger.info('Cron: running weekly alert matcher');
    const lastWeek = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000);
    const recent = await prisma.licitacao.findMany({
      where: { criadoEm: { gte: lastWeek } },
      select: { id: true },
    });
    if (recent.length > 0) {
      await matchAlerts(recent.map(l => l.id), ['SEMANAL']);
    }
  });

  logger.info('Scraping scheduler started');
}
