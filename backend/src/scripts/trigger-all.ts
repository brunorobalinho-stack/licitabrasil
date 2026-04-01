/**
 * Trigger all scrapers immediately by adding jobs to the BullMQ queue.
 * Usage: npx tsx src/scripts/trigger-all.ts
 */
import { scheduleScrapingJob } from '../jobs/queues.js';
import { logger } from '../lib/logger.js';

const ALL_SCRAPERS = [
  { name: 'pncp', params: { pageSize: 50 } },
  { name: 'comprasnet', params: { pageSize: 50 } },
  { name: 'comprasnet-arp', params: {} },
  { name: 'comprasnet-contratos', params: {} },
  { name: 'dou', params: { pageSize: 20 } },
  { name: 'bec-sp', params: {} },
  { name: 'conlicitacao', params: { pageSize: 50 } },
  { name: 'licitacoes-e', params: {} },
  { name: 'querido-diario', params: { size: 50 } },
] as const;

async function main() {
  console.log(`\n🚀 Triggering all ${ALL_SCRAPERS.length} scrapers...\n`);

  for (const { name, params } of ALL_SCRAPERS) {
    await scheduleScrapingJob(name, params);
    console.log(`  ✓ ${name} scheduled`);
  }

  console.log(`\n✅ All ${ALL_SCRAPERS.length} scraper jobs queued. Worker will process them.\n`);
  process.exit(0);
}

main().catch((err) => {
  console.error('Failed to trigger scrapers:', err);
  process.exit(1);
});
