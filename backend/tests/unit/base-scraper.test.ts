import { describe, it, expect, vi, beforeEach } from 'vitest';

/**
 * Unit tests for BaseScraper normalization helpers, hash generation,
 * date parsing, and retry logic.
 *
 * We instantiate a minimal concrete subclass so we can test the protected
 * and public methods without hitting real APIs or Prisma.
 */

// ---------------------------------------------------------------------------
// Mock Prisma and logger before importing
// ---------------------------------------------------------------------------

vi.mock('../../src/lib/prisma.js', () => ({
  prisma: {
    fonteDados: {
      upsert: vi.fn().mockResolvedValue({}),
      update: vi.fn().mockResolvedValue({}),
    },
    licitacao: {
      findUnique: vi.fn().mockResolvedValue(null),
      create: vi.fn().mockResolvedValue({ id: 'test-id' }),
      update: vi.fn().mockResolvedValue({ id: 'test-id' }),
    },
  },
}));

// Also mock the corrected path (../lib/ from scrapers/)
vi.mock('../../src/lib/logger.js', () => ({
  logger: {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
    child: vi.fn().mockReturnValue({
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
    }),
  },
}));

vi.mock('@prisma/client', () => ({
  Prisma: {
    Decimal: class Decimal {
      constructor(public value: number) {}
      toString() { return String(this.value); }
    },
  },
  Modalidade: {
    PREGAO_ELETRONICO: 'PREGAO_ELETRONICO',
    PREGAO_PRESENCIAL: 'PREGAO_PRESENCIAL',
    CONCORRENCIA: 'CONCORRENCIA',
    CONCORRENCIA_ELETRONICA: 'CONCORRENCIA_ELETRONICA',
    TOMADA_DE_PRECOS: 'TOMADA_DE_PRECOS',
    CONVITE: 'CONVITE',
    CONCURSO: 'CONCURSO',
    LEILAO: 'LEILAO',
    DIALOGO_COMPETITIVO: 'DIALOGO_COMPETITIVO',
    DISPENSA: 'DISPENSA',
    INEXIGIBILIDADE: 'INEXIGIBILIDADE',
    CREDENCIAMENTO: 'CREDENCIAMENTO',
    RDC: 'RDC',
    OUTRA: 'OUTRA',
  },
  Esfera: {
    FEDERAL: 'FEDERAL',
    ESTADUAL: 'ESTADUAL',
    MUNICIPAL: 'MUNICIPAL',
  },
  StatusLicitacao: {
    PUBLICADA: 'PUBLICADA',
    ABERTA: 'ABERTA',
    EM_ANDAMENTO: 'EM_ANDAMENTO',
    SUSPENSA: 'SUSPENSA',
    ADIADA: 'ADIADA',
    ENCERRADA: 'ENCERRADA',
    ANULADA: 'ANULADA',
    REVOGADA: 'REVOGADA',
    DESERTA: 'DESERTA',
    FRACASSADA: 'FRACASSADA',
    HOMOLOGADA: 'HOMOLOGADA',
    ADJUDICADA: 'ADJUDICADA',
  },
  TipoLicitacao: {
    COMPRA: 'COMPRA',
    SERVICO: 'SERVICO',
    OBRA: 'OBRA',
    SERVICO_ENGENHARIA: 'SERVICO_ENGENHARIA',
    ALIENACAO: 'ALIENACAO',
    CONCESSAO: 'CONCESSAO',
    PERMISSAO: 'PERMISSAO',
    LOCACAO: 'LOCACAO',
    OUTRO: 'OUTRO',
  },
}));

import { BaseScraper, RawLicitacao, ScrapingParams } from '../../src/scrapers/base-scraper.js';
import { Esfera } from '@prisma/client';

// ---------------------------------------------------------------------------
// Concrete test subclass
// ---------------------------------------------------------------------------

class TestScraper extends BaseScraper {
  public items: RawLicitacao[] = [];

  constructor() {
    super(0); // no rate limit in tests
  }
  getName() { return 'TEST'; }
  getSourceUrl() { return 'https://test.example.com'; }
  getEsfera() { return Esfera.FEDERAL; }

  async fetchLicitacoes(_params: ScrapingParams): Promise<RawLicitacao[]> {
    return this.items;
  }

  // Expose protected helpers for testing
  public testParseDate(v: string | Date | null | undefined) { return this.parseDate(v); }
  public async testWithRetry<T>(fn: () => Promise<T>, label?: string) {
    return this.withRetry(fn, label);
  }
}

// ---------------------------------------------------------------------------
// Factory for a valid RawLicitacao
// ---------------------------------------------------------------------------

function makeRawLicitacao(overrides: Partial<RawLicitacao> = {}): RawLicitacao {
  return {
    numeroEdital: 'PE-001/2025',
    numeroProcesso: '12345/2025',
    codigoUASG: null,
    codigoPNCP: null,
    modalidade: 'pregão eletrônico',
    tipo: 'compra',
    natureza: null,
    regime: null,
    criterioJulgamento: null,
    orgao: 'Ministério da Saúde',
    orgaoSigla: 'MS',
    esfera: 'FEDERAL',
    uf: 'DF',
    municipio: 'Brasília',
    objeto: 'Aquisição de equipamentos hospitalares para UTI',
    objetoResumido: 'Aquisição de equipamentos hospitalares',
    valorEstimado: 1500000,
    valorMinimo: null,
    valorMaximo: null,
    dataPublicacao: '2025-01-15T10:00:00Z',
    dataAbertura: '2025-02-01T14:00:00Z',
    dataEncerramento: null,
    dataResultado: null,
    segmento: 'Saúde',
    cnae: [],
    palavrasChave: ['equipamentos', 'hospitalares', 'UTI'],
    urlEdital: 'https://example.com/edital.pdf',
    urlAnexos: [],
    status: 'aberta',
    situacao: null,
    fonteOrigem: 'TEST',
    urlOrigem: 'https://test.example.com/1',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('BaseScraper', () => {
  let scraper: TestScraper;

  beforeEach(() => {
    scraper = new TestScraper();
    vi.clearAllMocks();
  });

  // ---- normalizeModalidade ----

  describe('normalizeModalidade', () => {
    it('maps "pregão eletrônico" with accents', () => {
      expect(scraper.normalizeModalidade('pregão eletrônico')).toBe('PREGAO_ELETRONICO');
    });

    it('maps "pregao eletronico" without accents', () => {
      expect(scraper.normalizeModalidade('pregao eletronico')).toBe('PREGAO_ELETRONICO');
    });

    it('maps "Concorrência" (capitalized)', () => {
      expect(scraper.normalizeModalidade('Concorrência')).toBe('CONCORRENCIA');
    });

    it('maps "DISPENSA DE LICITAÇÃO" (uppercase + accents)', () => {
      expect(scraper.normalizeModalidade('dispensa de licitação')).toBe('DISPENSA');
    });

    it('maps "tomada de preços"', () => {
      expect(scraper.normalizeModalidade('tomada de preços')).toBe('TOMADA_DE_PRECOS');
    });

    it('returns OUTRA for unknown strings', () => {
      expect(scraper.normalizeModalidade('algo desconhecido')).toBe('OUTRA');
    });

    it('returns OUTRA for empty string', () => {
      expect(scraper.normalizeModalidade('')).toBe('OUTRA');
    });
  });

  // ---- normalizeStatus ----

  describe('normalizeStatus', () => {
    it('maps "aberta"', () => {
      expect(scraper.normalizeStatus('aberta')).toBe('ABERTA');
    });

    it('maps masculine form "encerrado"', () => {
      expect(scraper.normalizeStatus('encerrado')).toBe('ENCERRADA');
    });

    it('maps "em andamento"', () => {
      expect(scraper.normalizeStatus('em andamento')).toBe('EM_ANDAMENTO');
    });

    it('maps "homologada"', () => {
      expect(scraper.normalizeStatus('homologada')).toBe('HOMOLOGADA');
    });

    it('defaults to PUBLICADA for unknown', () => {
      expect(scraper.normalizeStatus('status inventado')).toBe('PUBLICADA');
    });

    it('defaults to PUBLICADA for empty', () => {
      expect(scraper.normalizeStatus('')).toBe('PUBLICADA');
    });
  });

  // ---- normalizeTipo ----

  describe('normalizeTipo', () => {
    it('maps "compra"', () => {
      expect(scraper.normalizeTipo('compra')).toBe('COMPRA');
    });

    it('maps "serviço" with accent', () => {
      expect(scraper.normalizeTipo('serviço')).toBe('SERVICO');
    });

    it('maps "serviço de engenharia"', () => {
      expect(scraper.normalizeTipo('serviço de engenharia')).toBe('SERVICO_ENGENHARIA');
    });

    it('maps "obra"', () => {
      expect(scraper.normalizeTipo('obra')).toBe('OBRA');
    });

    it('maps "locação" with accent', () => {
      expect(scraper.normalizeTipo('locação')).toBe('LOCACAO');
    });

    it('returns OUTRO for unknown', () => {
      expect(scraper.normalizeTipo('xyz')).toBe('OUTRO');
    });
  });

  // ---- generateHash ----

  describe('generateHash', () => {
    it('produces a 64-char hex SHA-256', () => {
      const raw = makeRawLicitacao();
      const hash = scraper.generateHash(raw);
      expect(hash).toMatch(/^[a-f0-9]{64}$/);
    });

    it('same input produces same hash (deterministic)', () => {
      const raw = makeRawLicitacao();
      expect(scraper.generateHash(raw)).toBe(scraper.generateHash(raw));
    });

    it('different objeto produces different hash', () => {
      const a = makeRawLicitacao({ objeto: 'Aquisição A' });
      const b = makeRawLicitacao({ objeto: 'Aquisição B' });
      expect(scraper.generateHash(a)).not.toBe(scraper.generateHash(b));
    });

    it('different orgao produces different hash', () => {
      const a = makeRawLicitacao({ orgao: 'Órgão A' });
      const b = makeRawLicitacao({ orgao: 'Órgão B' });
      expect(scraper.generateHash(a)).not.toBe(scraper.generateHash(b));
    });

    it('handles null numeroEdital gracefully', () => {
      const raw = makeRawLicitacao({ numeroEdital: null });
      expect(() => scraper.generateHash(raw)).not.toThrow();
    });

    it('handles Date dataPublicacao', () => {
      const raw = makeRawLicitacao({ dataPublicacao: new Date('2025-01-15') });
      const hash = scraper.generateHash(raw);
      expect(hash).toMatch(/^[a-f0-9]{64}$/);
    });
  });

  // ---- parseDate ----

  describe('parseDate', () => {
    it('parses ISO string', () => {
      const result = scraper.testParseDate('2025-06-15T10:00:00Z');
      expect(result).toBeInstanceOf(Date);
      expect(result!.toISOString()).toContain('2025-06-15');
    });

    it('parses date-only string', () => {
      const result = scraper.testParseDate('2025-01-10');
      expect(result).toBeInstanceOf(Date);
    });

    it('returns null for null/undefined', () => {
      expect(scraper.testParseDate(null)).toBeNull();
      expect(scraper.testParseDate(undefined)).toBeNull();
    });

    it('returns null for invalid string', () => {
      expect(scraper.testParseDate('not-a-date')).toBeNull();
    });

    it('returns the Date as-is if valid', () => {
      const d = new Date('2025-03-01');
      expect(scraper.testParseDate(d)).toBe(d);
    });

    it('returns null for Invalid Date object', () => {
      expect(scraper.testParseDate(new Date('xyz'))).toBeNull();
    });
  });

  // ---- withRetry ----

  describe('withRetry', () => {
    it('returns on first success', async () => {
      const fn = vi.fn().mockResolvedValue('ok');
      const result = await scraper.testWithRetry(fn);
      expect(result).toBe('ok');
      expect(fn).toHaveBeenCalledTimes(1);
    });

    it('retries on failure then succeeds', async () => {
      const fn = vi.fn()
        .mockRejectedValueOnce(new Error('fail'))
        .mockResolvedValue('ok');
      const result = await scraper.testWithRetry(fn);
      expect(result).toBe('ok');
      expect(fn).toHaveBeenCalledTimes(2);
    });

    it('throws after max retries', async () => {
      const fn = vi.fn().mockRejectedValue(new Error('always fails'));
      await expect(scraper.testWithRetry(fn)).rejects.toThrow('always fails');
      expect(fn).toHaveBeenCalledTimes(3); // maxRetries = 3
    });
  });

  // ---- run() with deduplication ----

  describe('run() deduplication', () => {
    it('deduplicates items with the same hash', async () => {
      const { prisma } = await import('../../src/lib/prisma.js');

      const dup = makeRawLicitacao();
      scraper.items = [dup, { ...dup }]; // same data → same hash

      const result = await scraper.run();

      expect(result.total).toBe(2);
      // Only 1 unique item should be persisted
      expect(result.created + result.updated).toBe(1);
    });
  });
});
