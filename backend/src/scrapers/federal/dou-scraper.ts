import { Esfera } from '@prisma/client';
import * as cheerio from 'cheerio';
import type { Element } from 'domhandler';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';

// ---------------------------------------------------------------------------
// DOU (Diário Oficial da União) Scraper
//
// Scrapes Seção 3 of the DOU (the section that publishes licitações) from
// the official portal in.gov.br.  There is no public JSON API, so we parse
// the server-rendered HTML returned by the search endpoint.
// ---------------------------------------------------------------------------

const DOU_BASE = 'https://www.in.gov.br';
const DOU_SEARCH = `${DOU_BASE}/consulta/-/buscar/dou`;

export class DOUScraper extends BaseScraper {
  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 3000); // 3s — be extra polite with gov portals
  }

  getName(): string {
    return 'DOU';
  }

  getSourceUrl(): string {
    return 'https://www.in.gov.br/web/dou';
  }

  getEsfera(): Esfera {
    return Esfera.FEDERAL;
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    const results: RawLicitacao[] = [];
    const delta = Math.min(params.pageSize ?? 20, 75); // DOU max ~75
    const query = params.query ?? 'aviso de licitação';

    // Date filter: 'dia' (today), 'semana', 'mes', or 'personalizado'
    const exactDate = params.exactDate as string ?? 'dia';

    let start = 0;
    let hasMore = true;

    this.logger.info({ query, exactDate, delta }, 'Fetching licitacoes from DOU');

    while (hasMore) {
      const url = this.buildUrl(query, exactDate, delta, start);
      this.logger.debug({ url, start }, 'Requesting DOU search page');

      let html: string;
      try {
        html = await this.withRetry(async () => {
          const res = await fetch(url, {
            headers: {
              Accept: 'text/html',
              'User-Agent': 'LicitaBrasil/1.0 (+https://licitabrasil.com.br)',
            },
          });
          if (!res.ok) throw new Error(`DOU returned ${res.status}`);
          return res.text();
        }, `DOU start=${start}`);
      } catch (err) {
        this.logger.error({ err, start }, 'Failed to fetch DOU page');
        break;
      }

      const items = this.parseSearchResults(html);

      if (items.length === 0) {
        hasMore = false;
        break;
      }

      results.push(...items);

      this.logger.info(
        { start, items: items.length, totalSoFar: results.length },
        'DOU page fetched',
      );

      // Stop after reasonable limit to avoid hammering the portal
      if (items.length < delta || results.length >= 500) {
        hasMore = false;
      } else {
        start += delta;
        await this.rateLimit();
      }
    }

    this.logger.info({ total: results.length }, 'DOU fetch complete');
    return results;
  }

  // ---- Private helpers ----

  private buildUrl(query: string, exactDate: string, delta: number, start: number): string {
    const searchParams = new URLSearchParams({
      q: `"${query}"`,
      s: 'do3',          // Seção 3 = licitações, contratos, avisos
      exactDate,
      sortType: '0',
      delta: String(delta),
      start: String(start),
    });
    return `${DOU_SEARCH}?${searchParams.toString()}`;
  }

  parseSearchResults(html: string): RawLicitacao[] {
    const $ = cheerio.load(html);
    const items: RawLicitacao[] = [];

    // Each DOU result is in a .resultado-busca-dou or similar container
    const resultCards = $('div.resultado-busca-dou, div.resultados-item, section.resultado');

    // Fallback: if the Liferay-based portal uses a different class, try the broader selector
    const cards = resultCards.length > 0
      ? resultCards
      : $('[class*="resultado"]').filter(function () {
          return $(this).find('a[href*="/web/dou/"]').length > 0 || $(this).find('a[href*="/-/"]').length > 0;
        });

    cards.each((_, el) => {
      try {
        const card = $(el);
        const item = this.parseCard($, card);
        if (item) items.push(item);
      } catch (err) {
        this.logger.debug({ err }, 'Failed to parse DOU card');
      }
    });

    return items;
  }

  private parseCard($: cheerio.CheerioAPI, card: cheerio.Cheerio<Element>): RawLicitacao | null {
    // Title and link
    const titleEl = card.find('a[href*="/web/dou/"], a[href*="/-/"], a.title-content, h5 a, p.title a');
    const titleText = titleEl.text().trim() || card.find('h5, .title, .title-content').first().text().trim();
    const href = titleEl.attr('href') ?? '';
    const urlOrigem = href.startsWith('http') ? href : (href ? `${DOU_BASE}${href}` : DOU_BASE);

    if (!titleText) return null;

    // Section / hierarchy: "SEÇÃO 3 | MINISTÉRIO DA SAÚDE | Secretaria-Executiva"
    const sectionText = card.find('.secao-dou, .hierarchy, .breadcrumb-area').text().trim();
    const orgao = this.extractOrgao(sectionText, titleText);

    // Summary / abstract
    const summary = card.find('.abstract-dou, .resumo, p.abstract').text().trim()
      || card.find('p').last().text().trim();

    // Publication date
    const dateText = card.find('.date-dou, .data, .publicado-dou-data').text().trim();
    const dataPublicacao = this.parseDataPublicacao(dateText);

    // Edition / page
    const editionText = card.find('.edicao-dou, .edition').text().trim();

    const objeto = summary || titleText;

    return {
      numeroEdital: this.extractNumeroEdital(objeto),
      numeroProcesso: this.extractNumeroProcesso(objeto),
      codigoUASG: this.extractUASG(objeto) ?? this.extractUASG(sectionText),
      codigoPNCP: null,
      modalidade: this.inferModalidadeDOU(objeto),
      tipo: this.inferTipo(objeto),  // inherited from BaseScraper
      natureza: null,
      regime: null,
      criterioJulgamento: null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: 'FEDERAL',
      uf: this.extractUfFromOrgao(orgao),
      municipio: null,
      objeto: objeto.slice(0, 1000),
      objetoResumido: objeto.slice(0, 200),
      valorEstimado: this.extractValor(objeto),
      valorMinimo: null,
      valorMaximo: null,
      dataPublicacao: dataPublicacao ?? new Date().toISOString().split('T')[0],
      dataAbertura: this.extractDataAbertura(objeto),
      dataEncerramento: null,
      dataResultado: null,
      segmento: null,
      cnae: [],
      palavrasChave: this.extractKeywords(objeto),
      urlEdital: null,
      urlAnexos: [],
      status: 'publicada',
      situacao: editionText || null,
      fonteOrigem: 'DOU',
      urlOrigem,
    };
  }

  private extractOrgao(sectionText: string, titleText: string): string {
    if (sectionText) {
      // Example: "SEÇÃO 3 | MINISTÉRIO DA SAÚDE | Secretaria de Atenção Primária"
      const parts = sectionText.split('|').map((s) => s.trim()).filter(Boolean);
      // Skip "SEÇÃO 3" and take the first actual org name
      const orgParts = parts.filter((p) => !p.match(/^se[çc][aã]o\s+\d/i));
      if (orgParts.length > 0) return orgParts.join(' - ');
    }
    // Fallback: try to extract from title
    return titleText.slice(0, 100);
  }

  private parseDataPublicacao(dateText: string): string | null {
    if (!dateText) return null;
    // Try DD/MM/YYYY
    const match = dateText.match(/(\d{2})[/.](\d{2})[/.](\d{4})/);
    if (match) return `${match[3]}-${match[2]}-${match[1]}`;
    // Try YYYY-MM-DD
    const iso = dateText.match(/(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return iso[0];
    return null;
  }

  // extractNumeroEdital, extractNumeroProcesso inherited from BaseScraper

  // inferModalidade (DOU-specific: uses inferModalidadeDOU alias), inferTipo, extractValor,
  // extractDataAbertura, extractUASG, extractSigla, extractKeywords inherited from BaseScraper

  private inferModalidadeDOU(text: string): string {
    return this.inferModalidade(text);
  }

  private extractUfFromOrgao(orgao: string): string | null {
    const UF_PATTERN = /\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b/;
    const m = orgao.match(UF_PATTERN);
    return m?.[1] ?? 'DF';
  }
}
