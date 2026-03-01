/**
 * Vitest global setup
 * Stubs environment variables so tests can import config modules safely.
 */

process.env.DATABASE_URL = 'postgresql://test:test@localhost:5432/licitabrasil_test';
process.env.REDIS_URL = 'redis://localhost:6379';
process.env.JWT_SECRET = 'test-jwt-secret-32-chars-minimum!!';
process.env.JWT_REFRESH_SECRET = 'test-refresh-secret-32-chars!!!!';
process.env.JWT_EXPIRES_IN = '15m';
process.env.JWT_REFRESH_EXPIRES_IN = '7d';
process.env.PORT = '3099';
process.env.NODE_ENV = 'test';
process.env.CORS_ORIGIN = 'http://localhost:5173';
process.env.PNCP_API_BASE = 'https://pncp.gov.br/api/consulta';
process.env.QUERIDO_DIARIO_API_BASE = 'https://queridodiario.ok.org.br/api';
process.env.SCRAPING_CONCURRENCY = '1';
process.env.SCRAPING_RATE_LIMIT_MS = '0';
process.env.LOG_LEVEL = 'silent';
