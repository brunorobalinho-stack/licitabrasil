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
        codigoUASG: null,
        codigoPNCP: null,
        modalidade,
        tipo: this.inferTipoFromExcerpt(cleanExcerpt),
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
        dataAbertura: this.extractDataAbertura(cleanExcerpt, gazette.date),
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

    // If no excerpts yielded results but the gazette has content,
    // create a single entry from the first excerpt
    if (items.length === 0 && texts.length > 0) {
      const combined = texts.join(' ').slice(0, 500);
      if (combined.length >= 30) {
        items.push({
          numeroEdital: null,
          numeroProcesso: null,
          codigoUASG: null,
          codigoPNCP: null,
          modalidade: 'OUTRA',
          tipo: null,
          natureza: null,
          regime: null,
          criterioJulgamento: null,
          orgao: gazette.territory_name ?? 'Município não identificado',
          orgaoSigla: null,
          esfera: 'MUNICIPAL',
          uf: this.normalizeUf(gazette.state_code),
          municipio: gazette.territory_name ?? null,
          objeto: combined,
          objetoResumido: combined.slice(0, 200),
          valorEstimado: null,
          valorMinimo: null,
          valorMaximo: null,
          dataPublicacao: gazette.date,
          dataAbertura: null,
          dataEncerramento: null,
          dataResultado: null,
          segmento: null,
          cnae: [],
          palavrasChave: this.extractKeywords(combined),
          urlEdital: null,
          urlAnexos: [],
          status: 'publicada',
          situacao: null,
          fonteOrigem: 'QUERIDO_DIARIO',
          urlOrigem: gazette.url,
        });
      }
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

  /**
   * Try to infer the modalidade from the excerpt text.
   */
  private inferModalidade(text: string): string {
    const lower = text.toLowerCase();
    if (lower.includes('pregão eletrônico') || lower.includes('pregao eletronico')) {
      return 'PREGAO_ELETRONICO';
    }
    if (lower.includes('pregão presencial') || lower.includes('pregao presencial')) {
      return 'PREGAO_PRESENCIAL';
    }
    if (lower.includes('pregão') || lower.includes('pregao')) {
      return 'PREGAO_ELETRONICO';
    }
    if (lower.includes('concorrência') || lower.includes('concorrencia')) {
      return 'CONCORRENCIA';
    }
    if (lower.includes('tomada de preço') || lower.includes('tomada de preco')) {
      return 'TOMADA_DE_PRECOS';
    }
    if (lower.includes('convite')) {
      return 'CONVITE';
    }
    if (lower.includes('dispensa')) {
      return 'DISPENSA';
    }
    if (lower.includes('inexigibilidade')) {
      return 'INEXIGIBILIDADE';
    }
    if (lower.includes('credenciamento')) {
      return 'CREDENCIAMENTO';
    }
    if (lower.includes('concurso')) {
      return 'CONCURSO';
    }
    if (lower.includes('leilão') || lower.includes('leilao')) {
      return 'LEILAO';
    }
    return 'OUTRA';
  }

  /**
   * Try to extract edital number from text using regex.
   * Looks for patterns like "Edital nº 001/2024", "Pregão 123/2024", etc.
   */
  private extractNumeroEdital(text: string): string | null {
    const patterns = [
      /edital\s*(?:n[°ºo.]?\s*)?(\d+[\/.]\d{4})/i,
      /preg[aã]o\s*(?:eletr[oô]nico\s*)?(?:n[°ºo.]?\s*)?(\d+[\/.]\d{4})/i,
      /concorr[eê]ncia\s*(?:n[°ºo.]?\s*)?(\d+[\/.]\d{4})/i,
      /tomada\s*de\s*pre[cç]os?\s*(?:n[°ºo.]?\s*)?(\d+[\/.]\d{4})/i,
      /carta\s*convite\s*(?:n[°ºo.]?\s*)?(\d+[\/.]\d{4})/i,
      /(?:n[°ºo.]?\s*)(\d{1,5}[\/.]\d{4})/i,
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1]) return match[1];
    }

    return null;
  }

  /**
   * Try to extract processo number from text.
   */
  private extractNumeroProcesso(text: string): string | null {
    const patterns = [
      /processo\s*(?:administrativo\s*)?(?:n[°ºo.]?\s*)?(\d+[\/.]\d{4})/i,
      /processo\s*(?:n[°ºo.]?\s*)?(\d{4,}[\/.]\d{2,4})/i,
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1]) return match[1];
    }

    return null;
  }

  /**
   * Try to extract a monetary value from the text.
   * Looks for patterns like "R$ 1.234.567,89" or "R$1234567.89"
   */
  private extractValor(text: string): number | null {
    const patterns = [
      /R\$\s*([\d.]+,\d{2})/,
      /valor\s*(?:estimado|global|total)?\s*(?:de\s*)?R\$\s*([\d.]+,\d{2})/i,
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1]) {
        const valueStr = match[1].replace(/\./g, '').replace(',', '.');
        const value = parseFloat(valueStr);
        if (!isNaN(value) && value > 0) return value;
      }
    }

    return null;
  }

  /**
   * Try to extract an opening date from the text.
   * Looks for patterns like "dia 15/01/2024", "abertura: 15.01.2024"
   */
  private extractDataAbertura(text: string, fallbackDate: string): string | null {
    const patterns = [
      /(?:abertura|sessão|sessao|realização)\s*(?:em|:)?\s*(\d{2}[\/.]?\d{2}[\/.]?\d{4})/i,
      /dia\s+(\d{2}[\/.]?\d{2}[\/.]?\d{4})/i,
    ];

    for (const pattern of patterns) {
      const match = text.match(pattern);
      if (match?.[1]) {
        const cleaned = match[1].replace(/\./g, '/');
        const parts = cleaned.split('/');
        if (parts.length === 3) {
          const [day, month, year] = parts;
          const isoDate = `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`;
          const d = new Date(isoDate);
          if (!isNaN(d.getTime())) return isoDate;
        }
      }
    }

    return null;
  }

  /**
   * Infer tipo from excerpt text.
   */
  private inferTipoFromExcerpt(text: string): string | null {
    const lower = text.toLowerCase();
    if (lower.includes('obra') || lower.includes('construção') || lower.includes('reforma')) {
      return 'obra';
    }
    if (lower.includes('serviço de engenharia') || lower.includes('servico de engenharia')) {
      return 'serviço de engenharia';
    }
    if (lower.includes('serviço') || lower.includes('servico') || lower.includes('prestação')) {
      return 'serviço';
    }
    if (lower.includes('locação') || lower.includes('locacao') || lower.includes('aluguel')) {
      return 'locação';
    }
    if (lower.includes('compra') || lower.includes('aquisição') || lower.includes('fornecimento')) {
      return 'compra';
    }
    return null;
  }

  /**
   * Normalize UF state code: ensure uppercase, 2 chars.
   */
  private normalizeUf(stateCode: string | null | undefined): string | null {
    if (!stateCode) return null;
    const code = stateCode.trim().toUpperCase();
    return code.length === 2 ? code : null;
  }

  /**
   * Extract keywords from text for search.
   */
  private extractKeywords(text: string): string[] {
    const stopwords = new Set([
      'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'sem', 'por', 'em',
      'que', 'uma', 'um', 'os', 'as', 'no', 'na', 'nos', 'nas', 'ao',
      'ou', 'e', 'a', 'o', 'se', 'não', 'mais', 'como', 'mas', 'foi',
      'ser', 'está', 'são', 'ter', 'sua', 'seu', 'seus', 'suas',
      'este', 'esta', 'esse', 'essa', 'aquele', 'aquela',
    ]);

    return text
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, ' ')
      .split(/\s+/)
      .filter((w) => w.length > 2 && !stopwords.has(w))
      .filter((w, i, arr) => arr.indexOf(w) === i)
      .slice(0, 20);
  }
}
