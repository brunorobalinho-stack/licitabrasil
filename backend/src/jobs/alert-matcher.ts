import { prisma } from '../lib/prisma.js';
import { logger } from '../lib/logger.js';
import { scheduleNotificationJob } from './queues.js';
import type { Alerta } from '@prisma/client';

/**
 * Match new licitacoes against active alerts by keyword overlap.
 * Called after a scraper completes to check real-time alerts,
 * or by cron for DIARIO/SEMANAL alerts.
 */
export async function matchAlerts(
  licitacaoIds: string[],
  frequencias: ('TEMPO_REAL' | 'DIARIO' | 'SEMANAL')[] = ['TEMPO_REAL'],
): Promise<number> {
  if (licitacaoIds.length === 0) return 0;

  const alertas = await prisma.alerta.findMany({
    where: {
      ativo: true,
      frequencia: { in: frequencias },
    },
  });

  if (alertas.length === 0) return 0;

  const licitacoes = await prisma.licitacao.findMany({
    where: { id: { in: licitacaoIds } },
    select: {
      id: true,
      objeto: true,
      palavrasChave: true,
      modalidade: true,
      esfera: true,
      uf: true,
      municipio: true,
      segmento: true,
      valorEstimado: true,
    },
  });

  let totalMatches = 0;

  for (const alerta of alertas) {
    const matched = licitacoes.filter(l => matchesAlerta(l, alerta));
    if (matched.length === 0) continue;

    // Filter out already-notified matches
    const existing = await prisma.alertaMatch.findMany({
      where: {
        alertaId: alerta.id,
        licitacaoId: { in: matched.map(m => m.id) },
      },
      select: { licitacaoId: true },
    });
    const existingIds = new Set(existing.map(e => e.licitacaoId));
    const newIds = matched.map(m => m.id).filter(id => !existingIds.has(id));

    if (newIds.length === 0) continue;

    await scheduleNotificationJob(alerta.id, newIds);
    totalMatches += newIds.length;

    logger.info({
      alertaId: alerta.id,
      matched: newIds.length,
    }, 'Alert matches found, notification scheduled');
  }

  return totalMatches;
}

function matchesAlerta(
  licitacao: {
    objeto: string;
    palavrasChave: string[];
    modalidade: string;
    esfera: string;
    uf: string | null;
    municipio: string | null;
    segmento: string | null;
    valorEstimado: any;
  },
  alerta: Alerta,
): boolean {
  // Keywords match: at least one keyword appears in objeto or palavrasChave
  if (alerta.palavrasChave.length > 0) {
    const text = `${licitacao.objeto} ${licitacao.palavrasChave.join(' ')}`.toLowerCase();
    const hasKeyword = alerta.palavrasChave.some(kw => text.includes(kw.toLowerCase()));
    if (!hasKeyword) return false;
  }

  // Modalidade filter
  if (alerta.modalidades.length > 0 && !alerta.modalidades.includes(licitacao.modalidade as any)) {
    return false;
  }

  // Esfera filter
  if (alerta.esferas.length > 0 && !alerta.esferas.includes(licitacao.esfera as any)) {
    return false;
  }

  // Estado filter
  if (alerta.estados.length > 0 && licitacao.uf && !alerta.estados.includes(licitacao.uf)) {
    return false;
  }

  // Municipio filter
  if (alerta.municipios.length > 0 && licitacao.municipio && !alerta.municipios.includes(licitacao.municipio)) {
    return false;
  }

  // Segmento filter
  if (alerta.segmentos.length > 0 && licitacao.segmento && !alerta.segmentos.includes(licitacao.segmento)) {
    return false;
  }

  // Valor range filter
  const valor = licitacao.valorEstimado ? Number(licitacao.valorEstimado) : null;
  if (valor !== null) {
    if (alerta.valorMinimo && valor < Number(alerta.valorMinimo)) return false;
    if (alerta.valorMaximo && valor > Number(alerta.valorMaximo)) return false;
  }

  return true;
}
