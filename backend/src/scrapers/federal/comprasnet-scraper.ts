import { Esfera } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';

// ---------------------------------------------------------------------------
// ComprasNet Scraper (via API Dados Abertos Compras.gov.br)
//
// Uses the official Dados Abertos API which aggregates both:
//   - modulo-contratacoes: Lei 14.133/21 (current procurements)
//   - modulo-legado: Lei 8.666/93 (historical data)
//
// This gives us richer data than the PNCP API alone, including amparo legal,
// modo de disputa, IBGE codes, and SRP (registro de preços) flags.
//
// Docs: https://dadosabertos.compras.gov.br/swagger-ui/index.html
// ---------------------------------------------------------------------------

const DADOS_ABERTOS_BASE = 'https://dadosabertos.compras.gov.br';
const CONTRATACOES_ENDPOINT = `${DADOS_ABERTOS_BASE}/modulo-contratacoes/1_consultarContratacoes_PNCP_14133`;

// Response shape from the Dados Abertos API
interface DadosAbertosItem {
  idCompra: string;
  numeroControlePNCP: string;
  orgaoEntidadeCnpj: string;
  orgaoEntidadeRazaoSocial: string;
  orgaoEntidadeEsferaId: string; // F, E, M, D
  unidadeOrgaoCodigoUnidade: string;
  unidadeOrgaoNomeUnidade: string;
  unidadeOrgaoUfSigla: string;
  unidadeOrgaoMunicipioNome: string;
  unidadeOrgaoCodigoIbge?: number;
  codigoModalidade: number;
  modalidadeNome: string;
  objetoCompra: string;
  valorTotalEstimado: number | null;
  valorTotalHomologado: number | null;
  dataPublicacaoPncp: string;
  dataAberturaPropostaPncp: string | null;
  dataEncerramentoPropostaPncp: string | null;
  situacaoCompraIdPncp: number;
  situacaoCompraNomePncp: string;
  amparoLegalNome: string | null;
  amparoLegalDescricao: string | null;
  modoDisputaNomePncp: string | null;
  processo: string | null;
  numeroCompra: string | null;
  srp: boolean;
  informacaoComplementar: string | null;
  tipoInstrumentoConvocatorioNome: string | null;
  orcamentoSigilosoDescricao: string | null;
  contratacaoExcluida: boolean;
}

interface DadosAbertosResponse {
  resultado: DadosAbertosItem[];
  totalRegistros: number;
  totalPaginas: number;
  paginasRestantes: number;
}

// ---------------------------------------------------------------------------

export class ComprasNetScraper extends BaseScraper {
  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 2000);
  }

  getName(): string {
    return 'COMPRASNET';
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
    const yesterday = new Date(now.getTime() - 24 * 60 * 60 * 1000);
    const dataInicial = params.dataInicio ?? yesterday.toISOString().split('T')[0];
    const dataFinal = params.dataFim ?? now.toISOString().split('T')[0];

    // Modalidades: 1=Leilão, 2=Diálogo Competitivo, 3=Concurso, 4=Concorrência, 5=Pregão, 6=Dispensa, 7=Inexigibilidade, 9=Credenciamento
    const modalidades = [5, 6, 4, 7, 9, 1, 2, 3];

    this.logger.info({ dataInicial, dataFinal }, 'Fetching ComprasNet licitacoes via Dados Abertos');

    for (const codModalidade of modalidades) {
      let pagina = params.page ?? 1;
      let hasMore = true;

      while (hasMore) {
        const url = this.buildUrl(dataInicial, dataFinal, pagina, codModalidade);

        let response: DadosAbertosResponse;
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
              throw new Error(`Dados Abertos returned ${res.status}: ${body.slice(0, 200)}`);
            }
            return res.json() as Promise<DadosAbertosResponse>;
          }, `ComprasNet mod=${codModalidade} page=${pagina}`);
        } catch (err) {
          this.logger.warn({ err, codModalidade, pagina }, 'Failed to fetch ComprasNet page');
          break;
        }

        const items = (response.resultado ?? []).filter(
          (item) => !item.contratacaoExcluida,
        );

        if (items.length === 0) {
          hasMore = false;
          break;
        }

        for (const item of items) {
          try {
            results.push(this.mapToRawLicitacao(item));
          } catch (err) {
            this.logger.warn({ err, pncpId: item.numeroControlePNCP }, 'Failed to map item');
          }
        }

        this.logger.info(
          { codModalidade, pagina, items: items.length, totalSoFar: results.length },
          'ComprasNet page fetched',
        );

        if (response.paginasRestantes <= 0) hasMore = false;
        else {
          pagina++;
          await this.rateLimit();
        }
      }

      await this.rateLimit();
    }

    this.logger.info({ total: results.length }, 'ComprasNet fetch complete');
    return results;
  }

  // ---- Helpers (public for testing) ----

  buildUrl(dataInicial: string, dataFinal: string, pagina: number, codModalidade: number): string {
    const searchParams = new URLSearchParams({
      dataPublicacaoPncpInicial: dataInicial,
      dataPublicacaoPncpFinal: dataFinal,
      codigoModalidade: String(codModalidade),
      pagina: String(pagina),
    });
    return `${CONTRATACOES_ENDPOINT}?${searchParams.toString()}`;
  }

  mapToRawLicitacao(item: DadosAbertosItem): RawLicitacao {
    const orgao = item.orgaoEntidadeRazaoSocial ?? 'Órgão não informado';
    const objeto = item.objetoCompra ?? 'Objeto não informado';
    const complemento = item.informacaoComplementar;
    const objetoFull = complemento ? `${objeto}\n${complemento}` : objeto;

    return {
      numeroEdital: item.numeroCompra ?? null,
      numeroProcesso: item.processo ?? null,
      codigoUASG: item.unidadeOrgaoCodigoUnidade ?? null,
      codigoPNCP: item.numeroControlePNCP ?? null,
      modalidade: item.modalidadeNome ?? 'Outra',
      tipo: this.inferTipo(objeto),
      natureza: item.amparoLegalNome ?? null,
      regime: item.modoDisputaNomePncp ?? null,
      criterioJulgamento: item.tipoInstrumentoConvocatorioNome ?? null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: this.mapEsfera(item.orgaoEntidadeEsferaId),
      uf: item.unidadeOrgaoUfSigla ?? null,
      municipio: item.unidadeOrgaoMunicipioNome ?? null,
      objeto: objetoFull.slice(0, 1000),
      objetoResumido: objeto.slice(0, 200),
      valorEstimado: item.valorTotalEstimado ?? null,
      valorMinimo: null,
      valorMaximo: item.valorTotalHomologado ?? null,
      dataPublicacao: item.dataPublicacaoPncp?.split('T')[0] ?? new Date().toISOString().split('T')[0],
      dataAbertura: item.dataAberturaPropostaPncp?.split('T')[0] ?? null,
      dataEncerramento: item.dataEncerramentoPropostaPncp?.split('T')[0] ?? null,
      dataResultado: null,
      segmento: item.srp ? 'SRP' : null,
      cnae: [],
      palavrasChave: this.extractKeywords(objeto),
      urlEdital: null,
      urlAnexos: [],
      status: this.mapSituacao(item.situacaoCompraIdPncp, item.situacaoCompraNomePncp),
      situacao: item.situacaoCompraNomePncp ?? null,
      fonteOrigem: 'COMPRASNET',
      urlOrigem: `https://pncp.gov.br/app/editais/${item.numeroControlePNCP}`,
    };
  }

  private mapEsfera(esferaId: string): string {
    const map: Record<string, string> = { F: 'FEDERAL', E: 'ESTADUAL', M: 'MUNICIPAL', D: 'FEDERAL' };
    return map[esferaId] ?? 'FEDERAL';
  }

  private mapSituacao(id?: number, nome?: string): string {
    if (id != null) {
      const map: Record<number, string> = {
        1: 'publicada', 2: 'aberta', 3: 'em andamento', 4: 'encerrada',
        5: 'suspensa', 6: 'anulada', 7: 'revogada', 8: 'homologada',
        9: 'adjudicada', 10: 'deserta',
      };
      if (map[id]) return map[id];
    }
    return nome?.toLowerCase() ?? 'publicada';
  }

  // inferTipo, extractSigla, extractKeywords inherited from BaseScraper
}
