import cron from 'node-cron';
import { scheduleScrapingJob } from '../jobs/queues.js';
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

  // Run initial scraping 30 s after startup
  setTimeout(async () => {
    logger.info('Running initial scraping jobs…');
    await scheduleScrapingJob('pncp', { pageSize: 50 });
  }, 30_000);

  logger.info('Scraping scheduler started');
}
