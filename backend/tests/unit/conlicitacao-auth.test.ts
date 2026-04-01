import { describe, it, expect, vi, beforeEach } from 'vitest';

const { mockLogger, mockChildLogger } = vi.hoisted(() => {
  const mockChildLogger = {
    info: vi.fn(),
    warn: vi.fn(),
    error: vi.fn(),
    debug: vi.fn(),
  };
  return {
    mockChildLogger,
    mockLogger: {
      info: vi.fn(),
      warn: vi.fn(),
      error: vi.fn(),
      debug: vi.fn(),
      child: vi.fn().mockReturnValue(mockChildLogger),
    },
  };
});

vi.mock('../../src/lib/logger.js', () => ({
  logger: mockLogger,
}));

vi.mock('../../src/config/env.js', () => ({
  env: {
    CONLICITACAO_EMAIL: 'test@example.com',
    CONLICITACAO_PASSWORD: 'testpass',
    CONLICITACAO_API_BASE: 'https://consultaonline.conlicitacao.com.br',
    SCRAPING_RATE_LIMIT_MS: 0,
    DATABASE_URL: 'test',
    REDIS_URL: 'test',
    JWT_SECRET: 'test',
    JWT_REFRESH_SECRET: 'test',
    JWT_EXPIRES_IN: '15m',
    JWT_REFRESH_EXPIRES_IN: '7d',
    PORT: 3099,
    NODE_ENV: 'test',
    CORS_ORIGIN: '*',
    PNCP_API_BASE: 'test',
    QUERIDO_DIARIO_API_BASE: 'test',
    SCRAPING_CONCURRENCY: 1,
    LOG_LEVEL: 'silent',
  },
}));

import { ConLicitacaoAuth } from '../../src/scrapers/agregadores/conlicitacao-auth.js';

describe('ConLicitacaoAuth', () => {
  let auth: ConLicitacaoAuth;

  beforeEach(() => {
    vi.clearAllMocks();
    auth = new ConLicitacaoAuth();
  });

  it('starts with no cached cookie', () => {
    expect(auth.hasCachedSession()).toBe(false);
  });

  it('caches cookie after manual set', () => {
    auth.setSessionCookie('test_session_value');
    expect(auth.hasCachedSession()).toBe(true);
    expect(auth.getSessionCookie()).toBe('test_session_value');
  });

  it('clears cache', () => {
    auth.setSessionCookie('test_session_value');
    auth.clearSession();
    expect(auth.hasCachedSession()).toBe(false);
  });

  it('builds auth headers with cookie', () => {
    auth.setSessionCookie('abc123');
    const headers = auth.getAuthHeaders();
    expect(headers['Cookie']).toBe('_boletim_web_session=abc123');
    expect(headers['Accept']).toBe('application/json');
  });

  it('throws when getting headers without session', () => {
    expect(() => auth.getAuthHeaders()).toThrow('Not authenticated');
  });
});
