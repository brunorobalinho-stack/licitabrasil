import { Esfera } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';
import { ConLicitacaoAuth } from './conlicitacao-auth.js';
import { env } from '../../config/env.js';

// ---------------------------------------------------------------------------
// ConLicitação API response types
// ---------------------------------------------------------------------------

interface ConLicitBidding {
  id: number;
  orgao_uasg: string | null;
  orgao_endereco: string | null;
  orgao_cidade: string | null;
  orgao_estado: string | null;
  orgao_cep: string | null;
  edital: string | null;
  edital_site: string | null;
  edital_tem: boolean;
  processo: string | null;
  valor_estimado: number | null;
  itens: string | null;
  datahora_prazo: string | null;
  datahora_abertura: string | null;
  data_validade: string | null;
  objeto: string | null;
  observacao: string | null;
  modified: string;
  created: string;
  fonte_id: number | null;
  edicts: Array<{ filename: string; url: string }>;
  has_electronic_trading: boolean;
  electronic_trading: { trading_id?: string } | null;
  public_body: { id?: number; nome: string; tipo_orgao_id?: number } | null;
  modality: { nome: string } | null;
  bidding_grouping: { descricao: string } | null;
  contracts: unknown[];
}

interface ConLicitResponse {
  total_entries: number;
  total_pages: number;
  page: number;
  biddings: ConLicitBidding[];
}

// ---------------------------------------------------------------------------
// Status mapping from bidding_grouping.descricao
// ---------------------------------------------------------------------------

const GROUPING_STATUS_MAP: Record<string, string> = {
  'NOVA': 'publicada',
  'ATUALIZADA': 'publicada',
  'VIGENTE': 'aberta',
  'EM ANDAMENTO': 'em andamento',
  'ENCERRADA': 'encerrada',
  'SUSPENSA': 'suspensa',
  'ADIADA': 'adiada',
  'ANULADA': 'anulada',
  'CANCELADA': 'anulada',
  'REVOGADA': 'revogada',
  'DESERTA': 'deserta',
  'FRACASSADA': 'fracassada',
  'HOMOLOGADA': 'homologada',
  'ADJUDICADA': 'adjudicada',
};

// ---------------------------------------------------------------------------
// ConLicitação Scraper
// ---------------------------------------------------------------------------

export class ConLicitacaoScraper extends BaseScraper {
  private readonly baseUrl: string;
  private readonly auth: ConLicitacaoAuth;

  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 2000); // 2s default — be respectful
    this.baseUrl = env.CONLICITACAO_API_BASE;
    this.auth = new ConLicitacaoAuth();
  }

  getName(): string {
    return 'CONLICITACAO';
  }

  getSourceUrl(): string {
    return 'https://consultaonline.conlicitacao.com.br';
  }

  getEsfera(): Esfera {
    // ConLicitação aggregates all esferas; default to FEDERAL,
    // but we infer per-item from the data when possible
    return Esfera.FEDERAL;
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    await this.auth.authenticate();

    const results: RawLicitacao[] = [];
    const perPage = Math.min(params.pageSize ?? 50, 50);

    // Default: last 24 hours
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const dataInicio = params.dataInicio ?? yesterday.toISOString().split('T')[0];
    const dataFim = params.dataFim ?? now.toISOString().split('T')[0];

    let page = params.page ?? 1;
    let hasMore = true;

    this.logger.info({ dataInicio, dataFim, perPage }, 'Fetching licitacoes from ConLicitação');

    while (hasMore) {
      const url = this.buildUrl(dataInicio, dataFim, page, perPage);
      this.logger.debug({ url, page }, 'Requesting ConLicitação page');

      let response: ConLicitResponse;
      try {
        response = await this.withRetry(async () => {
          const res = await fetch(url, { headers: this.auth.getAuthHeaders() });

          // Re-authenticate on session expiry
          if (res.status === 423 || res.status === 302) {
            this.logger.warn({ status: res.status }, 'Session expired, re-authenticating');
            this.auth.clearSession();
            await this.auth.authenticate();
            const retry = await fetch(url, { headers: this.auth.getAuthHeaders() });
            if (!retry.ok) {
              throw new Error(`ConLicitação API returned ${retry.status} after re-auth`);
            }
            return retry.json() as Promise<ConLicitResponse>;
          }

          if (!res.ok) {
            const body = await res.text().catch(() => '');
            throw new Error(`ConLicitação API returned ${res.status}: ${body.slice(0, 200)}`);
          }

          return res.json() as Promise<ConLicitResponse>;
        }, `ConLicitação page=${page}`);
      } catch (err) {
        this.logger.error({ err, page }, 'Failed to fetch ConLicitação page');
        break;
      }

      if (!response.biddings || response.biddings.length === 0) {
        hasMore = false;
        break;
      }

      for (const bidding of response.biddings) {
        try {
          results.push(this.mapToRawLicitacao(bidding));
        } catch (err) {
          this.logger.warn({ err, biddingId: bidding.id }, 'Failed to map ConLicitação bidding');
        }
      }

      this.logger.info(
        { page, items: response.biddings.length, totalSoFar: results.length, totalEntries: response.total_entries },
        'ConLicitação page fetched',
      );

      if (page >= response.total_pages) {
        hasMore = false;
      } else {
        page++;
        await this.rateLimit();
      }
    }

    this.logger.info({ total: results.length }, 'ConLicitação fetch complete');
    return results;
  }

  // ---- Private helpers ----

  private buildUrl(dataInicio: string, dataFim: string, page: number, perPage: number): string {
    const from = `${dataInicio}T00:00:00.000-03:00`;
    const to = `${dataFim}T23:59:59.000-03:00`;

    const searchParams = new URLSearchParams({
      page: String(page),
      per_page: String(perPage),
      'modified[from]': from,
      'modified[to]': to,
    });

    return `${this.baseUrl}/biddings.json?${searchParams.toString()}`;
  }

  private mapToRawLicitacao(b: ConLicitBidding): RawLicitacao {
    const orgao = b.public_body?.nome ?? 'Órgão não informado';
    const modalidade = b.modality?.nome ?? 'Outra';
    const status = GROUPING_STATUS_MAP[b.bidding_grouping?.descricao ?? ''] ?? 'publicada';

    return {
      numeroEdital: b.edital ?? null,
      numeroProcesso: b.processo ?? null,
      codigoUASG: b.orgao_uasg ?? null,
      codigoPNCP: null,
      modalidade,
      tipo: this.inferTipo(b.objeto ?? ''),
      natureza: null,
      regime: null,
      criterioJulgamento: null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: this.inferEsfera(orgao),
      uf: b.orgao_estado ?? null,
      municipio: b.orgao_cidade ?? null,
      objeto: b.objeto ?? 'Objeto não informado',
      objetoResumido: (b.objeto ?? '').slice(0, 200),
      valorEstimado: b.valor_estimado && b.valor_estimado > 0 ? b.valor_estimado : null,
      valorMinimo: null,
      valorMaximo: null,
      dataPublicacao: b.created,
      dataAbertura: b.datahora_abertura ?? null,
      dataEncerramento: b.datahora_prazo ?? null,
      dataResultado: null,
      segmento: null,
      cnae: [],
      palavrasChave: this.extractKeywords(b.objeto ?? ''),
      urlEdital: b.edital_site ?? null,
      urlAnexos: b.edicts?.map((e) => `${this.baseUrl}${e.url}`) ?? [],
      status,
      situacao: b.bidding_grouping?.descricao ?? null,
      fonteOrigem: 'CONLICITACAO',
      urlOrigem: `${this.baseUrl}/boletim_web/public/licitacoes/${b.id}`,
    };
  }

  // inferTipo, extractSigla, extractKeywords inherited from BaseScraper
}
