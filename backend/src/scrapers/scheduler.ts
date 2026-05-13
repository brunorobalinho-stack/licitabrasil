import cron from 'node-cron';
import { scheduleScrapingJob } from '../jobs/queues.js';
import { logger } from '../lib/logger.js';

// All cron triggers run in Bruno's operating timezone so log timestamps
// and cron expressions line up with the team's wall clock.
const SCHEDULE_OPTS = { timezone: 'America/Fortaleza' };

export function startScheduler(): void {
  // PNCP — every 30 minutes (API allows pageSize 10-50)
  cron.schedule('*/30 * * * *', async () => {
    logger.info('Cron: scheduling PNCP scraping');
    await scheduleScrapingJob('pncp', { pageSize: 50 });
  }, SCHEDULE_OPTS);

  // Querido Diário — every 6 hours
  cron.schedule('0 */6 * * *', async () => {
    logger.info('Cron: scheduling Querido Diário scraping');
    await scheduleScrapingJob('querido-diario', { size: 50 });
  }, SCHEDULE_OPTS);

  // Run initial scraping 30 s after startup, for BOTH sources.
  // Without QD here, the first municipal pass had to wait up to 6 h.
  setTimeout(async () => {
    logger.info('Running initial scraping jobs (PNCP + Querido Diário)…');
    await Promise.all([
      scheduleScrapingJob('pncp', { pageSize: 50 }),
      scheduleScrapingJob('querido-diario', { size: 50 }),
    ]);
  }, 30_000);

  logger.info({ timezone: SCHEDULE_OPTS.timezone }, 'Scraping scheduler started');
}
