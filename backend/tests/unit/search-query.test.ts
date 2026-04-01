import { describe, it, expect } from 'vitest';
import { sanitizeSearchQuery } from '../../src/lib/search-query.js';

describe('sanitizeSearchQuery', () => {
  it('joins words with & for AND semantics', () => {
    expect(sanitizeSearchQuery('agua potavel')).toBe('agua & potavel');
  });

  it('strips special characters', () => {
    expect(sanitizeSearchQuery('serviço@#$ limpeza!')).toBe('serviço & limpeza');
  });

  it('handles accented Portuguese characters', () => {
    expect(sanitizeSearchQuery('manutenção predial')).toBe('manutenção & predial');
  });

  it('converts quoted phrases to <-> (phrase search)', () => {
    expect(sanitizeSearchQuery('"agua potavel" tratamento')).toBe('agua <-> potavel & tratamento');
  });

  it('returns null for empty/whitespace input', () => {
    expect(sanitizeSearchQuery('')).toBeNull();
    expect(sanitizeSearchQuery('   ')).toBeNull();
  });

  it('returns null for input with only special characters', () => {
    expect(sanitizeSearchQuery('@#$%')).toBeNull();
  });

  it('handles single word', () => {
    expect(sanitizeSearchQuery('hospital')).toBe('hospital');
  });

  it('collapses multiple spaces', () => {
    expect(sanitizeSearchQuery('agua    potavel')).toBe('agua & potavel');
  });
});
