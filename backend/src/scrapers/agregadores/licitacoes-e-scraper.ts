import { Esfera } from '@prisma/client';
import * as cheerio from 'cheerio';
import type { Element } from 'domhandler';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';

// ---------------------------------------------------------------------------
// Licitações-e (Banco do Brasil) Scraper
//
// Scrapes the public search of the Licitações-e platform operated by
// Banco do Brasil.  The legacy version is a Java/JSP app at
// licitacoes-e.com.br.  We use the search endpoint that returns
// server-rendered HTML with a list of tenders.
// ---------------------------------------------------------------------------

const LICIT_BASE = 'https://www.licitacoes-e.com.br';
const LICIT_SEARCH = `${LICIT_BASE}/aop/pesquisar-licitacao.aop`;

export class LicitacoesEScraper extends BaseScraper {
  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 3000);
  }

  getName(): string {
    return 'LICITACOES_E';
  }

  getSourceUrl(): string {
    return 'https://www.licitacoes-e.com.br';
  }

  getEsfera(): Esfera {
    return Esfera.FEDERAL; // default; we infer per-item when possible
  }

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    const results: RawLicitacao[] = [];

    this.logger.info('Fetching licitacoes from Licitações-e');

    // Step 1: GET the search form page to capture any session/cookies
    let cookies = '';
    try {
      const initialRes = await this.withRetry(async () => {
        const res = await fetch(`${LICIT_SEARCH}?opcao=preencherPesquisar`, {
          headers: {
            Accept: 'text/html',
            'User-Agent': 'LicitaBrasil/1.0 (+https://licitabrasil.com.br)',
          },
          redirect: 'manual',
        });
        // Capture cookies for the session
        const setCookie = res.headers.getSetCookie?.() ?? [];
        cookies = setCookie.map((c: string) => c.split(';')[0]).join('; ');
        if (!res.ok && res.status !== 302) throw new Error(`Licitações-e returned ${res.status}`);
        return res.text();
      }, 'Licitações-e initial page');
    } catch (err) {
      this.logger.warn({ err }, 'Failed to load Licitações-e search page');
    }

    await this.rateLimit();

    // Step 2: POST the search to get published licitações
    // The search form uses situacao=4 (publicadas) and tipoPesquisa=2 (all types)
    const situacoes = [
      { code: '4', label: 'publicadas' },       // Published
      { code: '1', label: 'propostas abertas' }, // Open for proposals
      { code: '3', label: 'em andamento' },      // In progress
    ];

    for (const sit of situacoes) {
      try {
        const html = await this.withRetry(async () => {
          const formData = new URLSearchParams({
            opcao: 'pesquisar',
            situacao: sit.code,
            tipoPesquisa: '2', // All types
          });

          const res = await fetch(LICIT_SEARCH, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/x-www-form-urlencoded',
              'User-Agent': 'LicitaBrasil/1.0',
              Accept: 'text/html',
              ...(cookies ? { Cookie: cookies } : {}),
            },
            body: formData.toString(),
          });

          if (!res.ok) throw new Error(`Licitações-e POST returned ${res.status}`);
          return res.text();
        }, `Licitações-e situacao=${sit.code}`);

        const items = this.parseSearchResults(html);
        results.push(...items);

        this.logger.info(
          { situacao: sit.label, items: items.length },
          'Licitações-e search page fetched',
        );
      } catch (err) {
        this.logger.error({ err, situacao: sit.label }, 'Failed to fetch Licitações-e search');
      }

      await this.rateLimit();
    }

    this.logger.info({ total: results.length }, 'Licitações-e fetch complete');
    return results;
  }

  // ---- Private helpers ----

  parseSearchResults(html: string): RawLicitacao[] {
    const $ = cheerio.load(html);
    const items: RawLicitacao[] = [];

    // The results page typically shows a table or list of licitações
    // Look for result containers
    const rows = $('table.resultado tr, table#tabelaResultado tr, div.resultado-item, tr.linhaPar, tr.linhaImpar');

    if (rows.length === 0) {
      // Try broader selectors for the JSP-rendered table
      $('table tr').each((_, row) => {
        const text = $(row).text();
        if (text.match(/licitação|pregão|edital|órgão/i) && text.length > 50) {
          try {
            const item = this.parseRow($, $(row));
            if (item) items.push(item);
          } catch {
            // skip
          }
        }
      });
    } else {
      rows.each((_, row) => {
        try {
          const item = this.parseRow($, $(row));
          if (item) items.push(item);
        } catch (err) {
          this.logger.debug({ err }, 'Failed to parse Licitações-e row');
        }
      });
    }

    // Also try to parse summary cards if the page uses a card layout
    $('div.card-licitacao, div.item-resultado, li.resultado-item').each((_, el) => {
      try {
        const item = this.parseCard($, $(el));
        if (item) items.push(item);
      } catch {
        // skip
      }
    });

    return items;
  }

  private parseRow($: cheerio.CheerioAPI, row: cheerio.Cheerio<Element>): RawLicitacao | null {
    const cells = row.find('td');
    if (cells.length < 2) return null;

    const texts = cells.map((_, cell) => $(cell).text().trim()).get();
    const allText = texts.join(' ');
    if (allText.length < 20) return null;

    // Skip header rows
    if (allText.match(/^(Licitação|N[°ºo]\s|Órgão|Objeto|Modalidade)\s/i) && cells.length > 4) return null;

    const link = row.find('a[href]').first();
    const href = link.attr('href') ?? '';
    const urlOrigem = href.startsWith('http') ? href : (href ? `${LICIT_BASE}${href}` : LICIT_BASE);

    // Pick the longest text as the objeto (description), not the first >30 chars
    const longest = [...texts].sort((a, b) => b.length - a.length)[0];
    const objeto = longest && longest.length > 20 ? longest : allText;
    const numeroEdital = this.extractNumeroLicitacao(texts);

    return this.buildRawLicitacao(objeto, numeroEdital, urlOrigem, texts);
  }

  private parseCard($: cheerio.CheerioAPI, card: cheerio.Cheerio<Element>): RawLicitacao | null {
    const text = card.text().trim();
    if (text.length < 30) return null;

    const link = card.find('a[href]').first();
    const href = link.attr('href') ?? '';
    const urlOrigem = href.startsWith('http') ? href : (href ? `${LICIT_BASE}${href}` : LICIT_BASE);

    return this.buildRawLicitacao(text, null, urlOrigem, []);
  }

  private buildRawLicitacao(
    objeto: string,
    numeroEdital: string | null,
    urlOrigem: string,
    texts: string[],
  ): RawLicitacao {
    const orgao = this.extractOrgao(texts) ?? 'Órgão não identificado';

    return {
      numeroEdital,
      numeroProcesso: this.extractNumeroProcesso(objeto),
      codigoUASG: this.extractUASG(objeto),
      codigoPNCP: null,
      modalidade: this.inferModalidadeLicitE(objeto),
      tipo: this.inferTipo(objeto),
      natureza: null,
      regime: null,
      criterioJulgamento: null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: this.inferEsfera(orgao),
      uf: this.extractUf(texts),
      municipio: null,
      objeto: objeto.slice(0, 1000),
      objetoResumido: objeto.slice(0, 200),
      valorEstimado: this.extractValor(objeto),
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
      fonteOrigem: 'LICITACOES_E',
      urlOrigem,
    };
  }

  private extractNumeroLicitacao(texts: string[]): string | null {
    for (const t of texts) {
      const m = t.match(/(\d{5,}\/\d{4})/);
      if (m) return m[1];
      const m2 = t.match(/(\d+[\/.]\d{4})/);
      if (m2 && t.length < 30) return m2[1];
    }
    return null;
  }

  private extractOrgao(texts: string[]): string | null {
    for (const t of texts) {
      if (t.match(/(?:minist[eé]rio|secretaria|prefeitura|governo|universidade|tribunal|funda[çc][aã]o|instituto|empresa|companhia|autarquia|sesc|senai|sesi)/i) && t.length > 5) {
        return t.slice(0, 200);
      }
    }
    return null;
  }

  // extractNumeroProcesso, extractUASG, extractValor, extractDataAbertura,
  // extractSigla, extractKeywords, inferTipo, inferEsfera inherited from BaseScraper

  private extractUf(texts: string[]): string | null {
    const UF_PATTERN = /\b(AC|AL|AP|AM|BA|CE|DF|ES|GO|MA|MT|MS|MG|PA|PB|PR|PE|PI|RJ|RN|RS|RO|RR|SC|SP|SE|TO)\b/;
    for (const t of texts) {
      const m = t.match(UF_PATTERN);
      if (m) return m[1];
    }
    return null;
  }

  private inferModalidadeLicitE(text: string): string {
    const result = this.inferModalidade(text);
    // Licitações-e is primarily electronic auctions; default to pregão eletrônico
    return result === 'outra' ? 'pregão eletrônico' : result;
  }

  private extractDate(texts: string[]): string | null {
    for (const t of texts) {
      const m = t.match(/(\d{2})[/.](\d{2})[/.](\d{4})/);
      if (m) return `${m[3]}-${m[2]}-${m[1]}`;
    }
    return null;
  }
}
