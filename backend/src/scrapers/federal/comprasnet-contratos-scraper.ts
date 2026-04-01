import { Esfera } from '@prisma/client';
import { BaseScraper, RawLicitacao, ScrapingParams } from '../base-scraper.js';

// ---------------------------------------------------------------------------
// ComprasNet Contratos Scraper (Contratos Federais)
//
// Uses the Dados Abertos API endpoint: modulo-contratos/1_consultarContratos
// Required params: dataVigenciaInicialMin, dataVigenciaInicialMax (YYYY-MM-DD)
//
// Federal contracts include supplier info, contract values, and legal basis.
// Useful for competitive intelligence (who won, at what price, for how long).
//
// Docs: https://dadosabertos.compras.gov.br/swagger-ui/index.html
// ---------------------------------------------------------------------------

const DADOS_ABERTOS_BASE = 'https://dadosabertos.compras.gov.br';
const CONTRATOS_ENDPOINT = `${DADOS_ABERTOS_BASE}/modulo-contratos/1_consultarContratos`;

export interface ContratoItem {
  codigoCategoria: string;
  codigoModalidadeCompra: string;
  codigoOrgao: string;
  codigoSubcategoria: string | null;
  codigoTipo: string;
  codigoUnidadeGestora: string;
  codigoUnidadeGestoraOrigemContrato: string;
  codigoUnidadeRealizadoraCompra: string;
  contratoExcluido: boolean;
  dataHoraExclusao: string | null;
  dataHoraInclusao: string | null;
  dataVigenciaFinal: string;
  dataVigenciaInicial: string;
  idCompra: string;
  informacoesComplementares: string | null;
  niFornecedor: string;
  nomeCategoria: string;
  nomeModalidadeCompra: string;
  nomeOrgao: string;
  nomeRazaoSocialFornecedor: string;
  nomeSubcategoria: string | null;
  nomeTipo: string;
  nomeUnidadeGestora: string;
  nomeUnidadeGestoraOrigemContrato: string;
  nomeUnidadeRealizadoraCompra: string;
  numeroCompra: string;
  numeroContrato: string;
  numeroControlePncpContrato: string | null;
  numeroParcelas: number;
  objeto: string;
  processo: string | null;
  receitaDespesa: string;
  totalDespesasAcessorias: number | null;
  unidadesRequisitantes: string | null;
  valorAcumulado: number | null;
  valorGlobal: number | null;
  valorParcela: number | null;
}

interface ContratosResponse {
  resultado: ContratoItem[];
  totalRegistros: number;
  totalPaginas: number;
  paginasRestantes: number;
}

export class ComprasNetContratosScraper extends BaseScraper {
  constructor(rateLimitMs?: number) {
    super(rateLimitMs ?? 2000);
  }

  getName(): string {
    return 'COMPRASNET_CONTRATOS';
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

    this.logger.info({ dataMin, dataMax }, 'Fetching Contratos via Dados Abertos');

    let pagina = params.page ?? 1;
    let hasMore = true;

    while (hasMore) {
      const url = this.buildUrl(dataMin, dataMax, pagina);

      let response: ContratosResponse;
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
            throw new Error(`Contratos API returned ${res.status}: ${body.slice(0, 200)}`);
          }
          return res.json() as Promise<ContratosResponse>;
        }, `Contratos page=${pagina}`);
      } catch (err) {
        this.logger.warn({ err, pagina }, 'Failed to fetch Contratos page');
        break;
      }

      const items = (response.resultado ?? []).filter((item) => !item.contratoExcluido);

      if (items.length === 0) {
        hasMore = false;
        break;
      }

      for (const item of items) {
        try {
          results.push(this.mapToRawLicitacao(item));
        } catch (err) {
          this.logger.warn({ err, contrato: item.numeroContrato }, 'Failed to map Contrato');
        }
      }

      this.logger.info(
        { pagina, items: items.length, totalSoFar: results.length },
        'Contratos page fetched',
      );

      if (response.paginasRestantes <= 0) hasMore = false;
      else {
        pagina++;
        await this.rateLimit();
      }
    }

    this.logger.info({ total: results.length }, 'Contratos fetch complete');
    return results;
  }

  buildUrl(dataMin: string, dataMax: string, pagina: number): string {
    const searchParams = new URLSearchParams({
      dataVigenciaInicialMin: dataMin,
      dataVigenciaInicialMax: dataMax,
      pagina: String(pagina),
    });
    return `${CONTRATOS_ENDPOINT}?${searchParams.toString()}`;
  }

  mapToRawLicitacao(item: ContratoItem): RawLicitacao {
    const orgao = item.nomeOrgao ?? item.nomeUnidadeGestora ?? 'Órgão não informado';
    const objeto = item.objeto ?? 'Objeto não informado';
    const complemento = item.informacoesComplementares;
    const objetoFull = complemento ? `${objeto}\n${complemento}` : objeto;
    const fornecedor = item.nomeRazaoSocialFornecedor;

    return {
      numeroEdital: item.numeroContrato ?? null,
      numeroProcesso: item.processo ?? null,
      codigoUASG: item.codigoUnidadeGestora ?? null,
      codigoPNCP: item.numeroControlePncpContrato ?? null,
      modalidade: item.nomeModalidadeCompra ?? 'Outra',
      tipo: this.mapCategoria(item.nomeCategoria),
      natureza: item.nomeTipo ?? null,
      regime: null,
      criterioJulgamento: null,
      orgao,
      orgaoSigla: this.extractSigla(orgao),
      esfera: this.inferEsfera(orgao),
      uf: null,
      municipio: null,
      objeto: objetoFull.slice(0, 1000),
      objetoResumido: objeto.slice(0, 200),
      valorEstimado: item.valorGlobal ?? item.valorAcumulado ?? null,
      valorMinimo: item.valorParcela ?? null,
      valorMaximo: item.valorGlobal ?? null,
      dataPublicacao: item.dataVigenciaInicial?.split('T')[0] ?? new Date().toISOString().split('T')[0],
      dataAbertura: null,
      dataEncerramento: item.dataVigenciaFinal?.split('T')[0] ?? null,
      dataResultado: null,
      segmento: fornecedor ? `Fornecedor: ${fornecedor}` : null,
      cnae: [],
      palavrasChave: this.extractKeywords(objeto),
      urlEdital: null,
      urlAnexos: [],
      status: 'homologada',
      situacao: 'Contrato vigente',
      fonteOrigem: 'COMPRASNET_CONTRATOS',
      urlOrigem: item.numeroControlePncpContrato
        ? `https://pncp.gov.br/app/contratos/${item.numeroControlePncpContrato}`
        : `https://dadosabertos.compras.gov.br/modulo-contratos/1.1_consultarContratos_Id?id=${item.idCompra}`,
    };
  }

  private mapCategoria(categoria: string): string {
    if (!categoria) return 'outro';
    const lower = categoria.toLowerCase();
    if (lower.includes('obra')) return 'obra';
    if (lower.includes('engenharia')) return 'serviço de engenharia';
    if (lower.includes('serviço') || lower.includes('servico')) return 'serviço';
    if (lower.includes('compra') || lower.includes('fornecimento')) return 'compra';
    if (lower.includes('locação') || lower.includes('locacao') || lower.includes('aluguel')) return 'locação';
    if (lower.includes('alienação') || lower.includes('alienacao')) return 'alienação';
    return 'outro';
  }

  // extractSigla, extractKeywords inherited from BaseScraper
}
