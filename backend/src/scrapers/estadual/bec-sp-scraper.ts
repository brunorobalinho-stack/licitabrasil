import { Esfera } from '@prisma/client';
import * as cheerio from 'cheerio';
import type { Element } from 'domhandler';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';

// ---------------------------------------------------------------------------
// BEC SP (Bolsa Eletrônica de Compras) Scraper
//
// Scrapes the public search page of the BEC/SP.  The site is an ASP.NET
// WebForms application that uses ViewState and __doPostBack.  Our approach:
//   1. GET the search page to obtain __VIEWSTATE / __EVENTVALIDATION
//   2. POST the search form to retrieve results
//   3. Parse the results table with cheerio
// ---------------------------------------------------------------------------

const BEC_BASE = 'https://www.bec.sp.gov.br';
const BEC_PREGAO_SEARCH = `${BEC_BASE}/bec_pregao_UI/OC/pesquisa_publica.aspx`;

export class BECSPScraper extends BaseScraper {
  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 3000);
  }

  getName(): string {
    return 'BEC_SP';
  }

  getSourceUrl(): string {
    return 'https://www.bec.sp.gov.br';
  }

  getEsfera(): Esfera {
    return Esfera.ESTADUAL;
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    const results: RawLicitacao[] = [];

    this.logger.info('Fetching licitacoes from BEC SP');

    // Step 1: GET the page to obtain ViewState
    let pageHtml: string;
    try {
      pageHtml = await this.withRetry(async () => {
        const res = await fetch(`${BEC_PREGAO_SEARCH}?chave=`, {
          headers: {
            Accept: 'text/html',
            'User-Agent': 'LicitaBrasil/1.0 (+https://licitabrasil.com.br)',
          },
        });
        if (!res.ok) throw new Error(`BEC SP returned ${res.status}`);
        return res.text();
      }, 'BEC SP initial page');
    } catch (err) {
      this.logger.error({ err }, 'Failed to load BEC SP search page');
      return results;
    }

    // Extract form state
    const formState = this.extractFormState(pageHtml);
    if (!formState.__VIEWSTATE) {
      this.logger.warn('No __VIEWSTATE found, attempting to parse initial page results');
      // Some pages already show results without postback
      const items = this.parseResultsTable(pageHtml);
      results.push(...items);
      return results;
    }

    await this.rateLimit();

    // Step 2: POST the search to get results
    const searchQuery = params.query ?? '';
    try {
      const postHtml = await this.withRetry(async () => {
        const formData = new URLSearchParams({
          __VIEWSTATE: formState.__VIEWSTATE,
          __VIEWSTATEGENERATOR: formState.__VIEWSTATEGENERATOR ?? '',
          __EVENTVALIDATION: formState.__EVENTVALIDATION ?? '',
          __EVENTTARGET: '',
          __EVENTARGUMENT: '',
          'ctl00$ContentPlaceHolder1$txtChave': searchQuery,
          'ctl00$ContentPlaceHolder1$btnPesquisar': 'Pesquisar',
        });

        const res = await fetch(`${BEC_PREGAO_SEARCH}?chave=`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'LicitaBrasil/1.0',
          },
          body: formData.toString(),
        });
        if (!res.ok) throw new Error(`BEC SP POST returned ${res.status}`);
        return res.text();
      }, 'BEC SP search POST');

      const items = this.parseResultsTable(postHtml);
      results.push(...items);
    } catch (err) {
      this.logger.error({ err }, 'Failed to submit BEC SP search');
      // Fallback: try to parse initial page anyway
      const items = this.parseResultsTable(pageHtml);
      results.push(...items);
    }

    this.logger.info({ total: results.length }, 'BEC SP fetch complete');
    return results;
  }

  // ---- Private helpers ----

  extractFormState(html: string): Record<string, string> {
    const $ = cheerio.load(html);
    return {
      __VIEWSTATE: $('input[name="__VIEWSTATE"]').val() as string ?? '',
      __VIEWSTATEGENERATOR: $('input[name="__VIEWSTATEGENERATOR"]').val() as string ?? '',
      __EVENTVALIDATION: $('input[name="__EVENTVALIDATION"]').val() as string ?? '',
    };
  }

  parseResultsTable(html: string): RawLicitacao[] {
    const $ = cheerio.load(html);
    const items: RawLicitacao[] = [];

    // BEC tables: look for GridView/table elements with licitacao data
    const rows = $('table[id*="GridView"] tr, table[id*="grd"] tr, table.resultado tr').not(':first-child');

    // Also try generic result patterns
    const resultDivs = $('div[id*="resultado"], div.item-licitacao, div.item-pregao');

    if (rows.length > 0) {
      rows.each((_, row) => {
        try {
          const item = this.parseTableRow($, $(row));
          if (item) items.push(item);
        } catch (err) {
          this.logger.debug({ err }, 'Failed to parse BEC row');
        }
      });
    }

    if (resultDivs.length > 0) {
      resultDivs.each((_, div) => {
        try {
          const item = this.parseResultDiv($, $(div));
          if (item) items.push(item);
        } catch (err) {
          this.logger.debug({ err }, 'Failed to parse BEC result div');
        }
      });
    }

    // Fallback: try to find any table with relevant content
    if (items.length === 0) {
      $('table tr').each((_, row) => {
        const text = $(row).text();
        if (text.includes('Pregão') || text.includes('OC') || text.includes('Dispensa')) {
          try {
            const item = this.parseGenericRow($, $(row));
            if (item) items.push(item);
          } catch {
            // skip
          }
        }
      });
    }

    return items;
  }

  private parseTableRow($: cheerio.CheerioAPI, row: cheerio.Cheerio<Element>): RawLicitacao | null {
    const cells = row.find('td');
    if (cells.length < 3) return null;

    const texts = cells.map((_, cell) => $(cell).text().trim()).get();
    const link = row.find('a[href]').first();
    const href = link.attr('href') ?? '';
    const urlOrigem = href.startsWith('http') ? href : (href ? `${BEC_BASE}${href}` : BEC_BASE);

    // Try to identify columns: typically OC#, Objeto, Órgão, Abertura, Valor
    const objeto = texts.find((t) => t.length > 30) ?? texts.slice(1).join(' ');
    if (!objeto || objeto.length < 10) return null;

    const numeroEdital = texts[0]?.match(/\d+/) ? texts[0] : null;

    return this.buildRawLicitacao(objeto, numeroEdital, urlOrigem, texts);
  }

  private parseResultDiv($: cheerio.CheerioAPI, div: cheerio.Cheerio<Element>): RawLicitacao | null {
    const text = div.text().trim();
    if (text.length < 30) return null;

    const link = div.find('a[href]').first();
    const href = link.attr('href') ?? '';
    const urlOrigem = href.startsWith('http') ? href : (href ? `${BEC_BASE}${href}` : BEC_BASE);

    return this.buildRawLicitacao(text, null, urlOrigem, []);
  }

  private parseGenericRow($: cheerio.CheerioAPI, row: cheerio.Cheerio<Element>): RawLicitacao | null {
    const text = row.text().trim();
    if (text.length < 30) return null;

    const link = row.find('a[href]').first();
    const href = link.attr('href') ?? '';
    const urlOrigem = href.startsWith('http') ? href : (href ? `${BEC_BASE}${href}` : BEC_BASE);

    return this.buildRawLicitacao(text, null, urlOrigem, []);
  }

  private buildRawLicitacao(objeto: string, numeroEdital: string | null, urlOrigem: string, texts: string[]): RawLicitacao {
    const allText = [objeto, ...texts].join(' ');
    return {
      numeroEdital,
      numeroProcesso: this.extractNumeroProcesso(objeto),
      codigoUASG: this.extractUASG(allText) ?? this.extractUGE(allText) ?? this.extractOC(urlOrigem),
      codigoPNCP: null,
      modalidade: this.inferModalidadeBEC(objeto),
      tipo: this.inferTipo(objeto),
      natureza: null,
      regime: null,
      criterioJulgamento: null,
      orgao: this.extractOrgao(texts) ?? 'Governo do Estado de São Paulo',
      orgaoSigla: 'BECSP',
      esfera: 'ESTADUAL',
      uf: 'SP',
      municipio: 'São Paulo',
      objeto: objeto.slice(0, 1000),
      objetoResumido: objeto.slice(0, 200),
      valorEstimado: this.extractValor(objeto) ?? this.extractValorFromTexts(texts),
      valorMinimo: null,
      valorMaximo: null,
      dataPublicacao: this.extractDate(texts) ?? new Date().toISOString().split('T')[0],
      dataAbertura: this.extractDataAbertura(objeto),
      dataEncerramento: null,
      dataResultado: null,
      segmento: null,
      cnae: [],
      palavrasChave: this.extractKeywords(objeto),
      urlEdital: null,
      urlAnexos: [],
      status: 'publicada',
      situacao: null,
      fonteOrigem: 'BEC_SP',
      urlOrigem,
    };
  }

  private extractOrgao(texts: string[]): string | null {
    // Find texts matching org patterns, prefer shorter ones (org name cells are concise)
    const candidates = texts.filter((t) =>
      t.match(/secretaria|funda[çc][aã]o|governo|prefeitura|universidade|instituto/i) && t.length > 5
    );
    if (candidates.length === 0) return null;
    candidates.sort((a, b) => a.length - b.length);
    return candidates[0].slice(0, 200);
  }

  // extractNumeroProcesso, inferTipo, extractValor, extractDataAbertura,
  // extractUASG, extractSigla, extractKeywords inherited from BaseScraper

  private inferModalidadeBEC(text: string): string {
    const lower = text.toLowerCase();
    if (lower.includes('pregão eletrônico') || lower.includes('pregao eletronico')) return 'pregão eletrônico';
    if (lower.includes('concorrência eletrônica') || lower.includes('concorrencia eletronica')) return 'concorrência eletrônica';
    if (lower.includes('pregão') || lower.includes('pregao') || lower.includes('oc ')) return 'pregão eletrônico';
    if (lower.includes('dispensa')) return 'dispensa';
    if (lower.includes('inexigibilidade')) return 'inexigibilidade';
    if (lower.includes('concorrência') || lower.includes('concorrencia')) return 'concorrência';
    if (lower.includes('credenciamento')) return 'credenciamento';
    return 'pregão eletrônico'; // BEC SP is primarily for pregões
  }

  private extractValorFromTexts(texts: string[]): number | null {
    for (const t of texts) {
      const v = this.extractValor(t);
      if (v) return v;
    }
    return null;
  }

  private extractDate(texts: string[]): string | null {
    for (const t of texts) {
      const m = t.match(/(\d{2})[/.](\d{2})[/.](\d{4})/);
      if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    }
    return null;
  }

  private extractUGE(text: string): string | null {
    const m = text.match(/(?:UGE|UC)\s*[:-]?\s*(\d{4,8})/i);
    return m?.[1] ?? null;
  }

  private extractOC(url: string): string | null {
    const m = url.match(/[?&](?:chave|oc|id)=(\d+)/i);
    return m?.[1] ?? null;
  }
}
