import { Worker, Job } from 'bullmq';
import { redis } from '../lib/redis.js';
import { logger } from '../lib/logger.js';
import { env } from '../config/env.js';
import { PNCPScraper } from '../scrapers/federal/pncp-scraper.js';
import { ComprasNetScraper } from '../scrapers/federal/comprasnet-scraper.js';
import { DOUScraper } from '../scrapers/federal/dou-scraper.js';
import { QueridoDiarioScraper } from '../scrapers/municipal/querido-diario.js';
import { BECSPScraper } from '../scrapers/estadual/bec-sp-scraper.js';
import { ConLicitacaoScraper } from '../scrapers/agregadores/conlicitacao-scraper.js';
import { LicitacoesEScraper } from '../scrapers/agregadores/licitacoes-e-scraper.js';
import { ComprasNetARPScraper } from '../scrapers/federal/comprasnet-arp-scraper.js';
import { ComprasNetContratosScraper } from '../scrapers/federal/comprasnet-contratos-scraper.js';
import { startScheduler } from '../scrapers/scheduler.js';
import { matchAlerts } from './alert-matcher.js';
import './notification-worker.js';
import type { BaseScraper, ScrapingResult } from '../scrapers/base-scraper.js';

// ---------------------------------------------------------------------------
// Scraper registry
// ---------------------------------------------------------------------------

const scraperFactory: Record<string, () => BaseScraper> = {
  pncp: () => new PNCPScraper(),
  PNCP: () => new PNCPScraper(),
  comprasnet: () => new ComprasNetScraper(),
  COMPRASNET: () => new ComprasNetScraper(),
  dou: () => new DOUScraper(),
  DOU: () => new DOUScraper(),
  'querido-diario': () => new QueridoDiarioScraper(),
  QUERIDO_DIARIO: () => new QueridoDiarioScraper(),
  'bec-sp': () => new BECSPScraper(),
  BEC_SP: () => new BECSPScraper(),
  conlicitacao: () => new ConLicitacaoScraper(),
  CONLICITACAO: () => new ConLicitacaoScraper(),
  'licitacoes-e': () => new LicitacoesEScraper(),
  LICITACOES_E: () => new LicitacoesEScraper(),
  'comprasnet-arp': () => new ComprasNetARPScraper(),
  COMPRASNET_ARP: () => new ComprasNetARPScraper(),
  'comprasnet-contratos': () => new ComprasNetContratosScraper(),
  COMPRASNET_CONTRATOS: () => new ComprasNetContratosScraper(),
};

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
    concurrency: env.SCRAPING_CONCURRENCY,
    limiter: { max: env.SCRAPING_CONCURRENCY, duration: env.SCRAPING_RATE_LIMIT_MS },
  },
);

worker.on('completed', async (job, result) => {
  logger.info({ jobId: job?.id, result }, 'Job completed');

  // Match new licitacoes against real-time alerts
  const scrapingResult = result as ScrapingResult | undefined;
  if (scrapingResult?.createdIds && scrapingResult.createdIds.length > 0) {
    try {
      const matched = await matchAlerts(scrapingResult.createdIds);
      if (matched > 0) {
        logger.info({ matched }, 'Alert matches scheduled for notification');
      }
    } catch (err) {
      logger.error({ err }, 'Error running alert matcher');
    }
  }
});

worker.on('failed', (job, err) => {
  logger.error({ jobId: job?.id, err: err.message }, 'Job failed');
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
