import { Esfera, Modalidade } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';
import { env } from '../../config/env.js';

// ---------------------------------------------------------------------------
// PNCP API response types
// ---------------------------------------------------------------------------

interface PNCPOrgaoEntidade {
  cnpj: string;
  razaoSocial: string;
  poderId?: string;
  esferaId?: string; // "F" = Federal, "E" = Estadual, "M" = Municipal
}

interface PNCPUnidadeOrgao {
  ufSigla?: string;
  ufNome?: string;
  municipioNome?: string;
  nomeUnidade?: string;
  codigoUnidade?: string;
  codigoIbge?: string;
}

interface PNCPItem {
  // Identification
  numeroControlePNCP: string;
  orgaoEntidade: PNCPOrgaoEntidade;
  unidadeOrgao?: PNCPUnidadeOrgao;
  anoCompra?: number;
  sequencialCompra?: number;
  numeroCompra?: string;
  processo?: string;
  codigoUasg?: string;

  // Classification
  modalidadeId: number;
  modalidadeNome?: string;
  tipoInstrumentoConvocatorioNome?: string;
  modoDisputaNome?: string;
  amparoLegal?: { codigo?: number; nome?: string; descricao?: string };
  criterioJulgamentoNome?: string;

  // Content
  objetoCompra: string;
  informacaoComplementar?: string;

  // Values
  valorTotalEstimado?: number;
  valorTotalHomologado?: number;

  // Dates
  dataPublicacaoPncp: string;
  dataAberturaProposta?: string;
  dataEncerramentoProposta?: string;
  dataResultado?: string;

  // Status
  situacaoCompraId?: number;
  situacaoCompraNome?: string;

  // Links
  linkSistemaOrigem?: string;
  linkProcessoEletronico?: string;

  // Flags
  srp?: boolean;
  dataInclusao?: string;
  dataAtualizacao?: string;
}

interface PNCPResponse {
  data?: PNCPItem[];
  totalRegistros?: number;
  totalPaginas?: number;
  paginaAtual?: number;
  // Alternative shape when pagination is in a different wrapper
  items?: PNCPItem[];
  total?: number;
}

// ---------------------------------------------------------------------------
// PNCP modalidade code to our enum mapping
// ---------------------------------------------------------------------------

const PNCP_MODALIDADE_MAP: Record<number, Modalidade> = {
  1: Modalidade.PREGAO_ELETRONICO,      // Leilão Eletrônico (new law) - map to pregao eletronico
  2: Modalidade.DIALOGO_COMPETITIVO,     // Diálogo Competitivo
  3: Modalidade.CONCURSO,                // Concurso
  4: Modalidade.CONCORRENCIA_ELETRONICA, // Concorrência - Eletrônica
  5: Modalidade.CONCORRENCIA,            // Concorrência - Presencial
  6: Modalidade.PREGAO_ELETRONICO,       // Pregão - Eletrônico
  7: Modalidade.PREGAO_PRESENCIAL,       // Pregão - Presencial
  8: Modalidade.DISPENSA,                // Dispensa de Licitação
  9: Modalidade.INEXIGIBILIDADE,         // Inexigibilidade
  10: Modalidade.LEILAO,                 // Leilão - Presencial (old)
  11: Modalidade.CREDENCIAMENTO,         // Credenciamento (Pré-qualificação)
  12: Modalidade.CREDENCIAMENTO,         // Credenciamento (Registro cadastral)
  13: Modalidade.OUTRA,                  // Manifestação de Interesse
};

// ---------------------------------------------------------------------------
// PNCP situação to status mapping
// ---------------------------------------------------------------------------

function mapSituacaoToStatus(situacaoId: number | undefined, situacaoNome: string | undefined): string {
  if (situacaoId != null) {
    switch (situacaoId) {
      case 1: return 'publicada';
      case 2: return 'aberta';
      case 3: return 'em andamento';
      case 4: return 'encerrada';
      case 5: return 'suspensa';
      case 6: return 'anulada';
      case 7: return 'revogada';
      case 8: return 'homologada';
      default: break;
    }
  }
  if (situacaoNome) {
    return situacaoNome.toLowerCase();
  }
  return 'publicada';
}

// ---------------------------------------------------------------------------
// PNCP Scraper
// ---------------------------------------------------------------------------

export class PNCPScraper extends BaseScraper {
  private readonly baseUrl: string;

  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? env.SCRAPING_RATE_LIMIT_MS);
    this.baseUrl = `${env.PNCP_API_BASE}/v1/contratacoes/publicacao`;
  }

  getName(): string {
    return 'PNCP';
  }

  getSourceUrl(): string {
    return 'https://pncp.gov.br';
  }

  getEsfera(): Esfera {
    return Esfera.FEDERAL;
  }

  // PNCP API requires codigoModalidadeContratacao, so we iterate over all.
  // Focus on the most common/relevant modalidades first.
  private static readonly MODALIDADE_CODES = [6, 8, 4, 9, 1, 5, 7, 11, 12, 2, 3, 10, 13];

  async fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]> {
    const results: RawLicitacao[] = [];
    const pageSize = Math.max(Math.min(params.pageSize ?? 50, 50), 10); // API: min=10, max=50

    // Default date range: last 24 hours
    const now = new Date();
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const dataInicial = params.dataInicio ?? yesterday.toISOString().split('T')[0];
    const dataFinal = params.dataFim ?? now.toISOString().split('T')[0];

    // If a specific modalidade is requested, only fetch that one
    const modalidades = params.codigoModalidadeContratacao
      ? [Number(params.codigoModalidadeContratacao)]
      : PNCPScraper.MODALIDADE_CODES;

    this.logger.info(
      { dataInicial, dataFinal, pageSize, modalidades: modalidades.length },
      'Fetching licitacoes from PNCP',
    );

    for (const codModalidade of modalidades) {
      let page = params.page ?? 1;
      let hasMore = true;

      while (hasMore) {
        const url = this.buildUrl(dataInicial, dataFinal, page, pageSize, codModalidade);
        this.logger.debug({ url, page, codModalidade }, 'Requesting PNCP page');

        let response: PNCPResponse;
        try {
          response = await this.withRetry(async () => {
            const res = await fetch(url, {
              headers: {
                'Accept': 'application/json',
                'User-Agent': 'LicitaBrasil/1.0',
              },
            });

            if (!res.ok) {
              const body = await res.text().catch(() => '');
              throw new Error(`PNCP API returned ${res.status}: ${body.slice(0, 200)}`);
            }

            return res.json() as Promise<PNCPResponse>;
          }, `PNCP modalidade=${codModalidade} page=${page}`);
        } catch (err) {
          this.logger.warn(
            { err, codModalidade, page },
            'Failed to fetch PNCP page, skipping modalidade',
          );
          break;
        }

        const items = response.data ?? response.items ?? [];

        if (items.length === 0) {
          hasMore = false;
          break;
        }

        for (const item of items) {
          try {
            const raw = this.mapToRawLicitacao(item);
            results.push(raw);
          } catch (err) {
            this.logger.warn(
              { err, pncpId: item.numeroControlePNCP },
              'Failed to map PNCP item',
            );
          }
        }

        this.logger.info(
          { codModalidade, page, itemsOnPage: items.length, totalSoFar: results.length },
          'PNCP page fetched',
        );

        // Determine if more pages exist
        const totalPages = response.totalPaginas;
        if (totalPages != null && page >= totalPages) {
          hasMore = false;
        } else if (items.length < pageSize) {
          hasMore = false;
        } else {
          page++;
          await this.rateLimit();
        }
      }

      // Rate limit between modalidades too
      await this.rateLimit();
    }

    this.logger.info({ total: results.length }, 'PNCP fetch complete');
    return results;
  }

  // ---- Private helpers ----

  private buildUrl(
    dataInicial: string,
    dataFinal: string,
    pagina: number,
    tamanhoPagina: number,
    codModalidade: number,
  ): string {
    const searchParams = new URLSearchParams({
      dataInicial: this.formatPNCPDate(dataInicial),
      dataFinal: this.formatPNCPDate(dataFinal),
      codigoModalidadeContratacao: String(codModalidade),
      pagina: String(pagina),
      tamanhoPagina: String(tamanhoPagina),
    });

    return `${this.baseUrl}?${searchParams.toString()}`;
  }

  /**
   * PNCP API expects dates in yyyyMMdd format.
   * Accepts ISO (YYYY-MM-DD) and converts.
   */
  private formatPNCPDate(dateStr: string): string {
    return dateStr.replace(/-/g, '');
  }

  private mapToRawLicitacao(item: PNCPItem): RawLicitacao {
    const orgao = item.orgaoEntidade?.razaoSocial ?? 'Orgão não informado';
    const uf = item.unidadeOrgao?.ufSigla ?? null;
    const municipio = item.unidadeOrgao?.municipioNome ?? null;
    const modalidade = PNCP_MODALIDADE_MAP[item.modalidadeId] ?? Modalidade.OUTRA;

    // Map esferaId: "F" → FEDERAL, "E" → ESTADUAL, "M" → MUNICIPAL
    const esferaId = item.orgaoEntidade?.esferaId?.toUpperCase();
    let esfera: string;
    if (esferaId === 'E') esfera = 'ESTADUAL';
    else if (esferaId === 'M') esfera = 'MUNICIPAL';
    else esfera = 'FEDERAL';

    const urlOrigem = item.linkSistemaOrigem
      ?? `https://pncp.gov.br/app/editais/${item.numeroControlePNCP}`;

    return {
      numeroEdital: item.numeroCompra ?? null,
      numeroProcesso: item.processo ?? null,
      codigoUASG: item.codigoUasg ?? null,
      codigoPNCP: item.numeroControlePNCP ?? null,
      modalidade: modalidade as string,
      tipo: this.inferTipo(item.objetoCompra),
      natureza: item.amparoLegal?.nome ?? null,
      regime: item.modoDisputaNome ?? null,
      criterioJulgamento: item.criterioJulgamentoNome ?? null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera,
      uf,
      municipio,
      objeto: item.objetoCompra ?? 'Objeto não informado',
      objetoResumido: (item.objetoCompra ?? '').slice(0, 200),
      valorEstimado: item.valorTotalEstimado ?? null,
      valorMinimo: null,
      valorMaximo: null,
      dataPublicacao: item.dataPublicacaoPncp,
      dataAbertura: item.dataAberturaProposta ?? null,
      dataEncerramento: item.dataEncerramentoProposta ?? null,
      dataResultado: item.dataResultado ?? null,
      segmento: null,
      cnae: [],
      palavrasChave: this.extractKeywords(item.objetoCompra ?? ''),
      urlEdital: item.linkProcessoEletronico ?? null,
      urlAnexos: [],
      status: mapSituacaoToStatus(item.situacaoCompraId, item.situacaoCompraNome),
      situacao: item.situacaoCompraNome ?? null,
      fonteOrigem: 'PNCP',
      urlOrigem,
    };
  }

  /**
   * Infer TipoLicitacao from the object text.
   */
  private inferTipo(objeto: string): string {
    if (!objeto) return 'outro';
    const lower = objeto.toLowerCase();
    if (lower.includes('obra') || lower.includes('construção') || lower.includes('reforma')) {
      return 'obra';
    }
    if (lower.includes('engenharia')) return 'serviço de engenharia';
    if (lower.includes('serviço') || lower.includes('servico') || lower.includes('prestação')) {
      return 'serviço';
    }
    if (lower.includes('locação') || lower.includes('locacao') || lower.includes('aluguel')) {
      return 'locação';
    }
    if (lower.includes('alienação') || lower.includes('alienacao') || lower.includes('venda')) {
      return 'alienação';
    }
    if (lower.includes('concessão') || lower.includes('concessao')) return 'concessão';
    return 'compra';
  }

  /**
   * Extract a rough sigla (abbreviation) from the organ name.
   * Takes first letter of each capitalized word.
   */
  private extractSigla(name: string): string {
    const words = name.split(/\s+/).filter((w) => w.length > 2);
    const sigla = words
      .map((w) => w[0])
      .join('')
      .toUpperCase()
      .slice(0, 10);
    return sigla || name.slice(0, 10).toUpperCase();
  }

  /**
   * Extract keywords from the object text for search purposes.
   */
  private extractKeywords(texto: string): string[] {
    const stopwords = new Set([
      'de', 'da', 'do', 'das', 'dos', 'para', 'com', 'sem', 'por', 'em',
      'que', 'uma', 'um', 'os', 'as', 'no', 'na', 'nos', 'nas', 'ao',
      'ou', 'e', 'a', 'o', 'se', 'não', 'mais', 'como', 'mas', 'foi',
      'ser', 'está', 'são', 'ter', 'sua', 'seu', 'seus', 'suas',
    ]);

    return texto
      .toLowerCase()
      .replace(/[^\p{L}\p{N}\s]/gu, ' ')
      .split(/\s+/)
      .filter((w) => w.length > 2 && !stopwords.has(w))
      .filter((w, i, arr) => arr.indexOf(w) === i)
      .slice(0, 20);
  }
}
