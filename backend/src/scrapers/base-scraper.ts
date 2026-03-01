import { createHash } from 'crypto';
import { Prisma, Modalidade, Esfera, StatusLicitacao, TipoLicitacao } from '@prisma/client';
import { prisma } from '../lib/prisma.js';
import { logger as rootLogger } from '../lib/logger.js';
import type { Logger } from 'pino';

// ---------------------------------------------------------------------------
// Interfaces
// ---------------------------------------------------------------------------

export interface RawLicitacao {
  numeroEdital: string | null;
  numeroProcesso: string | null;
  codigoUASG: string | null;
  codigoPNCP: string | null;
  modalidade: string;
  tipo: string | null;
  natureza: string | null;
  regime: string | null;
  criterioJulgamento: string | null;
  orgao: string;
  orgaoSigla: string | null;
  esfera: string;
  uf: string | null;
  municipio: string | null;
  objeto: string;
  objetoResumido: string | null;
  valorEstimado: number | null;
  valorMinimo: number | null;
  valorMaximo: number | null;
  dataPublicacao: string | Date;
  dataAbertura: string | Date | null;
  dataEncerramento: string | Date | null;
  dataResultado: string | Date | null;
  segmento: string | null;
  cnae: string[];
  palavrasChave: string[];
  urlEdital: string | null;
  urlAnexos: string[];
  status: string;
  situacao: string | null;
  fonteOrigem: string;
  urlOrigem: string;
}

export interface ScrapingParams {
  page?: number;
  pageSize?: number;
  dataInicio?: string;  // ISO date string YYYY-MM-DD
  dataFim?: string;     // ISO date string YYYY-MM-DD
  query?: string;
  [key: string]: unknown;
}

export interface ScrapingResult {
  source: string;
  total: number;
  created: number;
  updated: number;
  errors: number;
}

// ---------------------------------------------------------------------------
// Lookup tables for normalization
// ---------------------------------------------------------------------------

const MODALIDADE_MAP: Record<string, Modalidade> = {
  'pregao eletronico': Modalidade.PREGAO_ELETRONICO,
  'pregão eletrônico': Modalidade.PREGAO_ELETRONICO,
  'pregao': Modalidade.PREGAO_ELETRONICO,
  'pregão': Modalidade.PREGAO_ELETRONICO,
  'pregao presencial': Modalidade.PREGAO_PRESENCIAL,
  'pregão presencial': Modalidade.PREGAO_PRESENCIAL,
  'concorrencia': Modalidade.CONCORRENCIA,
  'concorrência': Modalidade.CONCORRENCIA,
  'concorrencia eletronica': Modalidade.CONCORRENCIA_ELETRONICA,
  'concorrência eletrônica': Modalidade.CONCORRENCIA_ELETRONICA,
  'tomada de precos': Modalidade.TOMADA_DE_PRECOS,
  'tomada de preços': Modalidade.TOMADA_DE_PRECOS,
  'convite': Modalidade.CONVITE,
  'concurso': Modalidade.CONCURSO,
  'leilao': Modalidade.LEILAO,
  'leilão': Modalidade.LEILAO,
  'dialogo competitivo': Modalidade.DIALOGO_COMPETITIVO,
  'diálogo competitivo': Modalidade.DIALOGO_COMPETITIVO,
  'dispensa': Modalidade.DISPENSA,
  'dispensa de licitacao': Modalidade.DISPENSA,
  'dispensa de licitação': Modalidade.DISPENSA,
  'dispensa eletronica': Modalidade.DISPENSA,
  'dispensa eletrônica': Modalidade.DISPENSA,
  'inexigibilidade': Modalidade.INEXIGIBILIDADE,
  'credenciamento': Modalidade.CREDENCIAMENTO,
  'rdc': Modalidade.RDC,
  'regime diferenciado': Modalidade.RDC,
  'outra': Modalidade.OUTRA,
};

const STATUS_MAP: Record<string, StatusLicitacao> = {
  'publicada': StatusLicitacao.PUBLICADA,
  'publicado': StatusLicitacao.PUBLICADA,
  'aberta': StatusLicitacao.ABERTA,
  'aberto': StatusLicitacao.ABERTA,
  'em andamento': StatusLicitacao.EM_ANDAMENTO,
  'em_andamento': StatusLicitacao.EM_ANDAMENTO,
  'suspensa': StatusLicitacao.SUSPENSA,
  'suspenso': StatusLicitacao.SUSPENSA,
  'adiada': StatusLicitacao.ADIADA,
  'adiado': StatusLicitacao.ADIADA,
  'encerrada': StatusLicitacao.ENCERRADA,
  'encerrado': StatusLicitacao.ENCERRADA,
  'anulada': StatusLicitacao.ANULADA,
  'anulado': StatusLicitacao.ANULADA,
  'revogada': StatusLicitacao.REVOGADA,
  'revogado': StatusLicitacao.REVOGADA,
  'deserta': StatusLicitacao.DESERTA,
  'deserto': StatusLicitacao.DESERTA,
  'fracassada': StatusLicitacao.FRACASSADA,
  'fracassado': StatusLicitacao.FRACASSADA,
  'homologada': StatusLicitacao.HOMOLOGADA,
  'homologado': StatusLicitacao.HOMOLOGADA,
  'adjudicada': StatusLicitacao.ADJUDICADA,
  'adjudicado': StatusLicitacao.ADJUDICADA,
};

const TIPO_MAP: Record<string, TipoLicitacao> = {
  'compra': TipoLicitacao.COMPRA,
  'compras': TipoLicitacao.COMPRA,
  'material': TipoLicitacao.COMPRA,
  'servico': TipoLicitacao.SERVICO,
  'serviço': TipoLicitacao.SERVICO,
  'servicos': TipoLicitacao.SERVICO,
  'serviços': TipoLicitacao.SERVICO,
  'obra': TipoLicitacao.OBRA,
  'obras': TipoLicitacao.OBRA,
  'servico de engenharia': TipoLicitacao.SERVICO_ENGENHARIA,
  'serviço de engenharia': TipoLicitacao.SERVICO_ENGENHARIA,
  'servicos de engenharia': TipoLicitacao.SERVICO_ENGENHARIA,
  'serviços de engenharia': TipoLicitacao.SERVICO_ENGENHARIA,
  'alienacao': TipoLicitacao.ALIENACAO,
  'alienação': TipoLicitacao.ALIENACAO,
  'concessao': TipoLicitacao.CONCESSAO,
  'concessão': TipoLicitacao.CONCESSAO,
  'permissao': TipoLicitacao.PERMISSAO,
  'permissão': TipoLicitacao.PERMISSAO,
  'locacao': TipoLicitacao.LOCACAO,
  'locação': TipoLicitacao.LOCACAO,
  'outro': TipoLicitacao.OUTRO,
  'outros': TipoLicitacao.OUTRO,
};

// ---------------------------------------------------------------------------
// Abstract Base Scraper
// ---------------------------------------------------------------------------

export abstract class BaseScraper {
  protected logger: Logger;
  protected rateLimitMs: number;
  private maxRetries = 3;
  private baseRetryDelayMs = 1000;

  constructor(rateLimitMs = 1000) {
    this.rateLimitMs = rateLimitMs;
    this.logger = rootLogger.child({ scraper: this.getName() });
  }

  // ---- Abstract methods ----
  abstract getName(): string;
  abstract getSourceUrl(): string;
  abstract getEsfera(): Esfera;
  abstract fetchLicitacoes(params: ScrapingParams): Promise<RawLicitacao[]>;

  // ---- Public entry point ----

  async run(params: ScrapingParams = {}): Promise<ScrapingResult> {
    const sourceName = this.getName();
    this.logger.info({ params }, `Starting scraping run for ${sourceName}`);

    const result: ScrapingResult = {
      source: sourceName,
      total: 0,
      created: 0,
      updated: 0,
      errors: 0,
    };

    try {
      // Update FonteDados to mark collection start
      await this.upsertFonteDados();
      await prisma.fonteDados.update({
        where: { nome: sourceName },
        data: { ultimaColeta: new Date() },
      });

      const rawItems = await this.fetchLicitacoes(params);
      result.total = rawItems.length;
      this.logger.info(`Fetched ${rawItems.length} raw items from ${sourceName}`);

      // Deduplicate by hashConteudo
      const seen = new Set<string>();
      const uniqueItems: RawLicitacao[] = [];
      for (const item of rawItems) {
        const hash = this.generateHash(item);
        if (!seen.has(hash)) {
          seen.add(hash);
          uniqueItems.push(item);
        }
      }
      this.logger.info(`${uniqueItems.length} unique items after deduplication`);

      // Persist each item
      for (const raw of uniqueItems) {
        try {
          const saved = await this.saveToDatabase(raw);
          if (saved === 'created') result.created++;
          else result.updated++;
        } catch (err) {
          result.errors++;
          this.logger.error({ err, raw: raw.numeroEdital ?? raw.objeto.slice(0, 80) }, 'Error saving licitacao');
        }
      }

      // Update FonteDados success stats
      await prisma.fonteDados.update({
        where: { nome: sourceName },
        data: {
          ultimoSucesso: new Date(),
          totalColetados: { increment: result.created + result.updated },
          totalErros: { increment: result.errors },
        },
      });

      this.logger.info({ result }, `Scraping run completed for ${sourceName}`);
    } catch (err) {
      this.logger.error({ err }, `Scraping run failed for ${sourceName}`);

      // Update FonteDados failure stats
      try {
        await prisma.fonteDados.update({
          where: { nome: sourceName },
          data: {
            ultimaFalha: new Date(),
            totalErros: { increment: 1 },
          },
        });
      } catch (updateErr) {
        this.logger.error({ err: updateErr }, 'Failed to update FonteDados on error');
      }

      throw err;
    }

    return result;
  }

  // ---- Hash generation ----

  generateHash(raw: RawLicitacao): string {
    const content = [
      raw.numeroEdital ?? '',
      raw.orgao,
      raw.objeto,
      raw.dataPublicacao instanceof Date
        ? raw.dataPublicacao.toISOString()
        : String(raw.dataPublicacao ?? ''),
    ].join('|');

    return createHash('sha256').update(content).digest('hex');
  }

  // ---- Normalization helpers ----

  normalizeModalidade(str: string): Modalidade {
    if (!str) return Modalidade.OUTRA;
    const key = str.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const keyAccented = str.trim().toLowerCase();
    return MODALIDADE_MAP[keyAccented] ?? MODALIDADE_MAP[key] ?? Modalidade.OUTRA;
  }

  normalizeEsfera(str: string): Esfera {
    if (!str) return this.getEsfera();
    const key = str.trim().toUpperCase();
    if (key === 'FEDERAL' || key === 'F') return Esfera.FEDERAL;
    if (key === 'ESTADUAL' || key === 'E') return Esfera.ESTADUAL;
    if (key === 'MUNICIPAL' || key === 'M') return Esfera.MUNICIPAL;
    return this.getEsfera();
  }

  normalizeStatus(str: string): StatusLicitacao {
    if (!str) return StatusLicitacao.PUBLICADA;
    const key = str.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const keyAccented = str.trim().toLowerCase();
    return STATUS_MAP[keyAccented] ?? STATUS_MAP[key] ?? StatusLicitacao.PUBLICADA;
  }

  normalizeTipo(str: string): TipoLicitacao {
    if (!str) return TipoLicitacao.OUTRO;
    const key = str.trim().toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
    const keyAccented = str.trim().toLowerCase();
    return TIPO_MAP[keyAccented] ?? TIPO_MAP[key] ?? TipoLicitacao.OUTRO;
  }

  // ---- Rate limiting ----

  protected async rateLimit(): Promise<void> {
    if (this.rateLimitMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, this.rateLimitMs));
    }
  }

  // ---- Retry with exponential backoff ----

  protected async withRetry<T>(fn: () => Promise<T>, label = 'request'): Promise<T> {
    let lastError: unknown;
    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        return await fn();
      } catch (err) {
        lastError = err;
        if (attempt < this.maxRetries) {
          const delay = this.baseRetryDelayMs * Math.pow(2, attempt - 1);
          this.logger.warn(
            { attempt, maxRetries: this.maxRetries, delay, err },
            `${label} failed, retrying in ${delay}ms`,
          );
          await new Promise((resolve) => setTimeout(resolve, delay));
        }
      }
    }
    throw lastError;
  }

  // ---- Parse date safely ----

  protected parseDate(value: string | Date | null | undefined): Date | null {
    if (!value) return null;
    if (value instanceof Date) return isNaN(value.getTime()) ? null : value;
    const d = new Date(value);
    return isNaN(d.getTime()) ? null : d;
  }

  // ---- Database persistence ----

  private async saveToDatabase(raw: RawLicitacao): Promise<'created' | 'updated'> {
    const hash = this.generateHash(raw);
    const dataPublicacao = this.parseDate(raw.dataPublicacao);
    if (!dataPublicacao) {
      throw new Error(`Invalid dataPublicacao for item: ${raw.numeroEdital ?? raw.objeto.slice(0, 60)}`);
    }

    const data: Prisma.LicitacaoCreateInput = {
      numeroEdital: raw.numeroEdital ?? null,
      numeroProcesso: raw.numeroProcesso ?? null,
      codigoUASG: raw.codigoUASG ?? null,
      codigoPNCP: raw.codigoPNCP ?? null,
      modalidade: this.normalizeModalidade(raw.modalidade),
      tipo: this.normalizeTipo(raw.tipo ?? ''),
      natureza: raw.natureza ?? null,
      regime: raw.regime ?? null,
      criterioJulgamento: raw.criterioJulgamento ?? null,
      orgao: raw.orgao,
      orgaoSigla: raw.orgaoSigla ?? null,
      esfera: this.normalizeEsfera(raw.esfera),
      uf: raw.uf ?? null,
      municipio: raw.municipio ?? null,
      objeto: raw.objeto,
      objetoResumido: raw.objetoResumido ?? raw.objeto.slice(0, 200),
      valorEstimado: raw.valorEstimado != null ? new Prisma.Decimal(raw.valorEstimado) : null,
      valorMinimo: raw.valorMinimo != null ? new Prisma.Decimal(raw.valorMinimo) : null,
      valorMaximo: raw.valorMaximo != null ? new Prisma.Decimal(raw.valorMaximo) : null,
      dataPublicacao,
      dataAbertura: this.parseDate(raw.dataAbertura),
      dataEncerramento: this.parseDate(raw.dataEncerramento),
      dataResultado: this.parseDate(raw.dataResultado),
      segmento: raw.segmento ?? null,
      cnae: raw.cnae ?? [],
      palavrasChave: raw.palavrasChave ?? [],
      urlEdital: raw.urlEdital ?? null,
      urlAnexos: raw.urlAnexos ?? [],
      status: this.normalizeStatus(raw.status),
      situacao: raw.situacao ?? null,
      fonteOrigem: raw.fonteOrigem,
      urlOrigem: raw.urlOrigem,
      hashConteudo: hash,
    };

    const existing = await prisma.licitacao.findUnique({
      where: { hashConteudo: hash },
      select: { id: true },
    });

    if (existing) {
      await prisma.licitacao.update({
        where: { hashConteudo: hash },
        data: {
          ...data,
          // Preserve the original id and hashConteudo
          hashConteudo: undefined,
        },
      });
      return 'updated';
    }

    await prisma.licitacao.create({ data });
    return 'created';
  }

  // ---- Ensure FonteDados record exists ----

  private async upsertFonteDados(): Promise<void> {
    await prisma.fonteDados.upsert({
      where: { nome: this.getName() },
      update: {},
      create: {
        nome: this.getName(),
        url: this.getSourceUrl(),
        tipo: 'API',
        esfera: this.getEsfera(),
        ativo: true,
        intervaloMinutos: 30,
      },
    });
  }
}
