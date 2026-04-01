import { scheduleScrapingJob } from '../src/jobs/queues.js';

async function main() {
  const scrapers: [string, Record<string, unknown>][] = [
    ['pncp', { pageSize: 50 }],
    ['comprasnet', { pageSize: 50 }],
    ['dou', { pageSize: 20 }],
    ['querido-diario', { size: 50 }],
    ['bec-sp', {}],
    ['licitacoes-e', {}],
    ['comprasnet-arp', {}],
    ['comprasnet-contratos', {}],
  ];

  for (const [name, params] of scrapers) {
    await scheduleScrapingJob(name, params);
    console.log(`Queued: ${name}`);
  }

  console.log('\nAll 8 scrapers queued (ConLicitacao skipped — requires credentials)');
  process.exit(0);
}

main();
