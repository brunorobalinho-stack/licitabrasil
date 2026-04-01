import { Esfera } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';
import { env } from '../../config/env.js';

// ---------------------------------------------------------------------------
// Querido Diário API response types
// ---------------------------------------------------------------------------

interface QDGazette {
  territory_id: string;
  territory_name: string;
  state_code: string;
  date: string;           // YYYY-MM-DD
  edition_number?: string;
  is_extra_edition: boolean;
  url: string;
  txt_url?: string;
  excerpts: string[];
  highlight_texts?: string[];
}

interface QDResponse {
  total_gazettes: number;
  gazettes: QDGazette[];
}

// ---------------------------------------------------------------------------
// Keywords used to identify licitacao-related content in gazette excerpts
// ---------------------------------------------------------------------------

const LICITACAO_KEYWORDS = [
  'licitação', 'licitacao',
  'pregão', 'pregao',
  'concorrência', 'concorrencia',
  'tomada de preço', 'tomada de preco',
  'carta convite',
  'dispensa de licitação', 'dispensa de licitacao',
  'inexigibilidade',
  'edital',
  'processo licitatório', 'processo licitatorio',
  'chamamento público', 'chamamento publico',
  'contratação direta', 'contratacao direta',
  'credenciamento',
  'diálogo competitivo', 'dialogo competitivo',
  'registro de preços', 'registro de precos',
  'ata de registro',
];

// ---------------------------------------------------------------------------
// Querido Diário Scraper
// ---------------------------------------------------------------------------

export class QueridoDiarioScraper extends BaseScraper {
  private readonly baseUrl: string;

  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? env.SCRAPING_RATE_LIMIT_MS);
    this.baseUrl = `${env.QUERIDO_DIARIO_API_BASE}/gazettes`;
  }

  getName(): string {
    return 'QUERIDO_DIARIO';
  }

  getSourceUrl(): string {
    return 'https://queridodiario.ok.org.br';
  }

  getEsfera(): Esfera {
    return Esfera.MUNICIPAL;
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    const results: RawLicitacao[] = [];
    const size = Math.min((params.pageSize ?? params.size ?? 100) as number, 100);

    // Default date range: last 7 days (gazette publication is less frequent)
    const now = new Date();
    const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
    const publishedSince = params.dataInicio ?? weekAgo.toISOString().split('T')[0];
    const publishedUntil = params.dataFim ?? now.toISOString().split('T')[0];

    // Search query: use a broad licitacao-related querystring
    const queryString = params.query ?? 'licitação edital pregão';

    let offset = (params.page != null ? (params.page - 1) * size : 0);
    let hasMore = true;

    this.logger.info(
      { publishedSince, publishedUntil, queryString, size },
      'Fetching gazettes from Querido Diário',
    );

    while (hasMore) {
      const url = this.buildUrl(queryString, publishedSince, publishedUntil, offset, size);
      this.logger.debug({ url, offset }, 'Requesting Querido Diário page');

      const response = await this.withRetry(async () => {
        const res = await fetch(url, {
          headers: {
            'Accept': 'application/json',
            'User-Agent': 'LicitaBrasil/1.0',
          },
        });

        if (!res.ok) {
          const body = await res.text().catch(() => '');
          throw new Error(`Querido Diário API returned ${res.status}: ${body.slice(0, 200)}`);
        }

        return res.json() as Promise<QDResponse>;
      }, `QD offset ${offset}`);

      const gazettes = response.gazettes ?? [];

      if (gazettes.length === 0) {
        hasMore = false;
        break;
      }

      for (const gazette of gazettes) {
        try {
          const rawItems = this.extractLicitacoesFromGazette(gazette);
          results.push(...rawItems);
        } catch (err) {
          this.logger.warn(
            { err, territoryId: gazette.territory_id, date: gazette.date },
            'Failed to extract from gazette',
          );
        }
      }

      this.logger.info(
        { offset, gazettesOnPage: gazettes.length, totalItems: results.length },
        'Querido Diário page fetched',
      );

      // Pagination: if we got fewer than requested, we're done
      if (gazettes.length < size) {
        hasMore = false;
      } else if (offset + size >= response.total_gazettes) {
        hasMore = false;
      } else {
        offset += size;
        await this.rateLimit();
      }
    }

    this.logger.info({ total: results.length }, 'Querido Diário fetch complete');
    return results;
  }

  // ---- Private helpers ----

  private buildUrl(
    querystring: string,
    publishedSince: string,
    publishedUntil: string,
    offset: number,
    size: number,
  ): string {
    const params = new URLSearchParams({
      querystring,
      published_since: publishedSince,
      published_until: publishedUntil,
      offset: String(offset),
      size: String(size),
      pre_tags: '',
      post_tags: '',
      sort_by: 'relevance',
    });

    return `${this.baseUrl}?${params.toString()}`;
  }

  /**
   * Extracts licitacao-like entries from a gazette's excerpts.
   * Each excerpt that contains licitacao keywords becomes a separate RawLicitacao.
   */
  private extractLicitacoesFromGazette(gazette: QDGazette): RawLicitacao[] {
    const items: RawLicitacao[] = [];

    // Combine excerpts and highlight_texts
    const texts = [
      ...(gazette.excerpts ?? []),
      ...(gazette.highlight_texts ?? []),
    ];

    if (texts.length === 0) {
      return items;
    }

    // Process each excerpt that mentions licitacao
    for (const excerpt of texts) {
      if (!this.containsLicitacaoKeyword(excerpt)) {
        continue;
      }

      const cleanExcerpt = this.cleanExcerpt(excerpt);
      if (cleanExcerpt.length < 30) continue; // too short to be useful

      const objeto = cleanExcerpt.slice(0, 500);
      const modalidade = this.inferModalidade(cleanExcerpt);
      const numeroEdital = this.extractNumeroEdital(cleanExcerpt);

      const raw: RawLicitacao = {
        numeroEdital,
        numeroProcesso: this.extractNumeroProcesso(cleanExcerpt),
        codigoUASG: this.extractUASG(cleanExcerpt) ?? gazette.territory_id ?? null,
        codigoPNCP: null,
        modalidade,
        tipo: this.inferTipo(cleanExcerpt),
        natureza: null,
        regime: null,
        criterioJulgamento: null,
        orgao: gazette.territory_name ?? 'Município não identificado',
        orgaoSigla: null,
        esfera: 'MUNICIPAL',
        uf: this.normalizeUf(gazette.state_code),
        municipio: gazette.territory_name ?? null,
        objeto,
        objetoResumido: objeto.slice(0, 200),
        valorEstimado: this.extractValor(cleanExcerpt),
        valorMinimo: null,
        valorMaximo: null,
        dataPublicacao: gazette.date,
        dataAbertura: this.extractDataAbertura(cleanExcerpt),
        dataEncerramento: null,
        dataResultado: null,
        segmento: null,
        cnae: [],
        palavrasChave: this.extractKeywords(cleanExcerpt),
        urlEdital: null,
        urlAnexos: [],
        status: 'publicada',
        situacao: null,
        fonteOrigem: 'QUERIDO_DIARIO',
        urlOrigem: gazette.url,
      };

      items.push(raw);
    }

    return items;
  }

  private containsLicitacaoKeyword(text: string): boolean {
    const lower = text.toLowerCase();
    return LICITACAO_KEYWORDS.some((kw) => lower.includes(kw));
  }

  /**
   * Remove HTML tags and clean up whitespace from excerpt.
   */
  private cleanExcerpt(text: string): string {
    return text
      .replace(/<[^>]*>/g, '')
      .replace(/\s+/g, ' ')
      .trim();
  }

  // inferModalidade inherited from BaseScraper

  // extractNumeroEdital, extractNumeroProcesso, extractValor, extractDataAbertura
  // inherited from BaseScraper

  // inferTipo inherited from BaseScraper (used as inferTipoFromExcerpt replacement)

  /**
   * Normalize UF state code: ensure uppercase, 2 chars.
   */
  private normalizeUf(stateCode: string | null | undefined): string | null {
    if (!stateCode) return null;
    const code = stateCode.trim().toUpperCase();
    return code.length === 2 ? code : null;
  }

  // extractUASG, extractKeywords inherited from BaseScraper
}
