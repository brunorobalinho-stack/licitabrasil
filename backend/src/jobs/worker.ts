import { Worker, Job } from 'bullmq';
import { redis } from '../lib/redis.js';
import { logger } from '../lib/logger.js';
import { PNCPScraper } from '../scrapers/federal/pncp-scraper.js';
import { QueridoDiarioScraper } from '../scrapers/municipal/querido-diario.js';
import { startScheduler } from '../scrapers/scheduler.js';
import type { ScrapingResult } from '../scrapers/base-scraper.js';

// ---------------------------------------------------------------------------
// Scraper registry
// ---------------------------------------------------------------------------

const scraperFactory: Record<string, () => PNCPScraper | QueridoDiarioScraper> = {
  pncp: () => new PNCPScraper(),
  PNCP: () => new PNCPScraper(),
  'querido-diario': () => new QueridoDiarioScraper(),
  QUERIDO_DIARIO: () => new QueridoDiarioScraper(),
};

// ---------------------------------------------------------------------------
// Consecutive-failure tracking (per sourceName)
// ---------------------------------------------------------------------------

const consecutiveFailures = new Map<string, number>();
const FAILURE_WARN_EVERY = 5;

function sourceFromJob(job: Job | undefined): string {
  return (job?.data as { sourceName?: string } | undefined)?.sourceName ?? 'unknown';
}

// ---------------------------------------------------------------------------
// Worker
// ---------------------------------------------------------------------------

const worker = new Worker(
  'scraping',
  async (job: Job) => {
    const { sourceName, params } = job.data as {
      sourceName: string;
      params: Record<string, unknown>;
    };

    logger.info({ jobId: job.id, sourceName }, 'Processing scraping job');

    const create = scraperFactory[sourceName];
    if (!create) throw new Error(`Unknown scraper: ${sourceName}`);

    const scraper = create();
    const result: ScrapingResult = await scraper.run(params ?? {});

    logger.info({ jobId: job.id, result }, 'Scraping job completed');
    return result;
  },
  {
    connection: redis as any,
    concurrency: 2,
    limiter: { max: 1, duration: 5000 },
  },
);

worker.on('completed', (job, result) => {
  const sourceName = sourceFromJob(job);
  if (consecutiveFailures.get(sourceName)) {
    consecutiveFailures.set(sourceName, 0);
  }
  logger.info({ jobId: job?.id, sourceName, result }, 'Job completed');
});

worker.on('failed', (job, err) => {
  const sourceName = sourceFromJob(job);
  const next = (consecutiveFailures.get(sourceName) ?? 0) + 1;
  consecutiveFailures.set(sourceName, next);

  logger.error(
    {
      jobId: job?.id,
      sourceName,
      consecutiveFailures: next,
      err: err.message,
      stack: err.stack,
    },
    'Scraping job failed',
  );

  if (next % FAILURE_WARN_EVERY === 0) {
    logger.warn(
      { sourceName, consecutiveFailures: next },
      `Scraper "${sourceName}" hit ${next} consecutive failures — investigate the source or rate limits`,
    );
  }
});

worker.on('error', (err) => {
  logger.error({ err }, 'Worker error');
});

// Start cron scheduler
startScheduler();

logger.info('LicitaBrasil scraping worker started');

// Graceful shutdown
const shutdown = async () => {
  logger.info('Worker shutting down…');
  await worker.close();
  process.exit(0);
};
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
