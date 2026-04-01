import { Esfera } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';

// ---------------------------------------------------------------------------
// ComprasNet ARP Scraper (Atas de Registro de Preço)
//
// Uses the Dados Abertos API endpoint: modulo-arp/1_consultarARP
// Required params: dataVigenciaInicialMin, dataVigenciaInicialMax (YYYY-MM-DD)
//
// ARPs are active price registration records that other entities can join
// ("carona"). This data is extremely valuable for suppliers looking for
// existing procurement opportunities.
//
// Docs: https://dadosabertos.compras.gov.br/swagger-ui/index.html
// ---------------------------------------------------------------------------

const DADOS_ABERTOS_BASE = 'https://dadosabertos.compras.gov.br';
const ARP_ENDPOINT = `${DADOS_ABERTOS_BASE}/modulo-arp/1_consultarARP`;

export interface ARPItem {
  anoCompra: string;
  ataExcluido: boolean;
  codigoModalidadeCompra: string;
  codigoOrgao: string | null;
  codigoUnidadeGerenciadora: string;
  dataAssinatura: string | null;
  dataHoraAtualizacao: string | null;
  dataHoraExclusao: string | null;
  dataHoraInclusao: string | null;
  dataVigenciaFinal: string;
  dataVigenciaInicial: string;
  idCompra: string;
  linkAtaPNCP: string | null;
  linkCompraPNCP: string | null;
  nomeModalidadeCompra: string;
  nomeOrgao: string | null;
  nomeUnidadeGerenciadora: string;
  numeroAtaRegistroPreco: string;
  numeroCompra: string;
  numeroControlePncpAta: string | null;
  numeroControlePncpCompra: string | null;
  objeto: string;
  quantidadeItens: number;
  statusAta: string;
  valorTotal: number | null;
}

interface ARPResponse {
  resultado: ARPItem[];
  totalRegistros: number;
  totalPaginas: number;
  paginasRestantes: number;
}

export class ComprasNetARPScraper extends BaseScraper {
  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 2000);
  }

  getName(): string {
    return 'COMPRASNET_ARP';
  }

  getSourceUrl(): string {
    return 'https://www.gov.br/compras';
  }

  getEsfera(): Esfera {
    return Esfera.FEDERAL;
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    const results: RawLicitacao[] = [];

    const now = new Date();
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
    const dataMin = params.dataInicio ?? thirtyDaysAgo.toISOString().split('T')[0];
    const dataMax = params.dataFim ?? now.toISOString().split('T')[0];

    this.logger.info({ dataMin, dataMax }, 'Fetching ARPs via Dados Abertos');

    let pagina = params.page ?? 1;
    let hasMore = true;

    while (hasMore) {
      const url = this.buildUrl(dataMin, dataMax, pagina);

      let response: ARPResponse;
      try {
        response = await this.withRetry(async () => {
          const res = await fetch(url, {
            headers: {
              Accept: 'application/json',
              'User-Agent': 'LicitaBrasil/1.0 (+https://licitabrasil.com.br)',
            },
          });
          if (!res.ok) {
            const body = await res.text().catch(() => '');
            throw new Error(`ARP API returned ${res.status}: ${body.slice(0, 200)}`);
          }
          return res.json() as Promise<ARPResponse>;
        }, `ARP page=${pagina}`);
      } catch (err) {
        this.logger.warn({ err, pagina }, 'Failed to fetch ARP page');
        break;
      }

      const items = (response.resultado ?? []).filter((item) => !item.ataExcluido);

      if (items.length === 0) {
        hasMore = false;
        break;
      }

      for (const item of items) {
        try {
          results.push(this.mapToRawLicitacao(item));
        } catch (err) {
          this.logger.warn({ err, ata: item.numeroAtaRegistroPreco }, 'Failed to map ARP item');
        }
      }

      this.logger.info(
        { pagina, items: items.length, totalSoFar: results.length },
        'ARP page fetched',
      );

      if (response.paginasRestantes <= 0) hasMore = false;
      else {
        pagina++;
        await this.rateLimit();
      }
    }

    this.logger.info({ total: results.length }, 'ARP fetch complete');
    return results;
  }

  buildUrl(dataMin: string, dataMax: string, pagina: number): string {
    const searchParams = new URLSearchParams({
      dataVigenciaInicialMin: dataMin,
      dataVigenciaInicialMax: dataMax,
      pagina: String(pagina),
    });
    return `${ARP_ENDPOINT}?${searchParams.toString()}`;
  }

  mapToRawLicitacao(item: ARPItem): RawLicitacao {
    const orgao = item.nomeUnidadeGerenciadora ?? item.nomeOrgao ?? 'Órgão não informado';
    const objeto = item.objeto ?? 'Objeto não informado';

    return {
      numeroEdital: item.numeroAtaRegistroPreco ?? null,
      numeroProcesso: null,
      codigoUASG: item.codigoUnidadeGerenciadora ?? null,
      codigoPNCP: item.numeroControlePncpAta ?? null,
      modalidade: item.nomeModalidadeCompra ?? 'Outra',
      tipo: this.inferTipo(objeto),
      natureza: null,
      regime: null,
      criterioJulgamento: null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: this.inferEsfera(orgao),
      uf: null,
      municipio: null,
      objeto: objeto.slice(0, 1000),
      objetoResumido: objeto.slice(0, 200),
      valorEstimado: item.valorTotal ?? null,
      valorMinimo: null,
      valorMaximo: null,
      dataPublicacao: item.dataVigenciaInicial?.split('T')[0] ?? new Date().toISOString().split('T')[0],
      dataAbertura: item.dataAssinatura?.split('T')[0] ?? null,
      dataEncerramento: item.dataVigenciaFinal?.split('T')[0] ?? null,
      dataResultado: null,
      segmento: 'SRP',
      cnae: [],
      palavrasChave: this.extractKeywords(objeto),
      urlEdital: item.linkAtaPNCP ?? null,
      urlAnexos: item.linkCompraPNCP ? [item.linkCompraPNCP] : [],
      status: this.mapStatus(item.statusAta),
      situacao: item.statusAta ?? null,
      fonteOrigem: 'COMPRASNET_ARP',
      urlOrigem: item.linkAtaPNCP ?? `https://dadosabertos.compras.gov.br/modulo-arp/1.1_consultarARP_Id?id=${item.idCompra}`,
    };
  }

  private mapStatus(statusAta: string): string {
    if (!statusAta) return 'publicada';
    const lower = statusAta.toLowerCase();
    if (lower.includes('vigente') || lower.includes('registro')) return 'aberta';
    if (lower.includes('cancelad')) return 'anulada';
    if (lower.includes('encerrad') || lower.includes('vencid') || lower.includes('substituíd')) return 'encerrada';
    if (lower.includes('suspens')) return 'suspensa';
    return 'publicada';
  }

  // inferTipo, extractSigla, extractKeywords inherited from BaseScraper
}
