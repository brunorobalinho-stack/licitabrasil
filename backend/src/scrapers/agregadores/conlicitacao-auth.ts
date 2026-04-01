import puppeteer from 'puppeteer';
import { env } from '../../config/env.js';
import { logger as rootLogger } from '../../lib/logger.js';

const logger = rootLogger.child({ module: 'conlicitacao-auth' });

export class ConLicitacaoAuth {
  private sessionCookie: string | null = null;
  private lastAuthAt: Date | null = null;
  private readonly maxSessionAgeMs = 30 * 60 * 1000; // 30 min

  hasCachedSession(): boolean {
    if (!this.sessionCookie) return false;
    if (this.lastAuthAt && Date.now() - this.lastAuthAt.getTime() > this.maxSessionAgeMs) {
      this.sessionCookie = null;
      this.lastAuthAt = null;
      return false;
    }
    return true;
  }

  getSessionCookie(): string | null {
    return this.sessionCookie;
  }

  setSessionCookie(cookie: string): void {
    this.sessionCookie = cookie;
    this.lastAuthAt = new Date();
  }

  clearSession(): void {
    this.sessionCookie = null;
    this.lastAuthAt = null;
  }

  getAuthHeaders(): Record<string, string> {
    if (!this.sessionCookie) {
      throw new Error('Not authenticated — call authenticate() first');
    }
    return {
      'Cookie': `_boletim_web_session=${this.sessionCookie}`,
      'Accept': 'application/json',
      'User-Agent': 'LicitaBrasil/1.0',
    };
  }

  /**
   * Log in via Puppeteer to obtain the httpOnly _boletim_web_session cookie.
   * The Rails app has CSRF protection, so we must use a real browser.
   */
  async authenticate(): Promise<void> {
    if (this.hasCachedSession()) {
      logger.debug('Using cached ConLicitação session');
      return;
    }

    logger.info('Authenticating with ConLicitação via Puppeteer');
    const browser = await puppeteer.launch({
      headless: true,
      args: ['--no-sandbox', '--disable-setuid-sandbox'],
    });

    try {
      const page = await browser.newPage();

      // Navigate to login page to get session cookie + CSRF
      await page.goto(`${env.CONLICITACAO_API_BASE}/users/login`, {
        waitUntil: 'networkidle2',
        timeout: 30_000,
      });

      // Fill login form and submit
      await page.evaluate(
        (email, password) => {
          return fetch('/users/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `user[email]=${encodeURIComponent(email)}&user[password]=${encodeURIComponent(password)}`,
            credentials: 'same-origin',
            redirect: 'manual',
          }).then((r) => r.status);
        },
        env.CONLICITACAO_EMAIL,
        env.CONLICITACAO_PASSWORD,
      );

      // Extract the session cookie
      const cookies = await page.cookies();
      const sessionCookie = cookies.find((c) => c.name === '_boletim_web_session');

      if (!sessionCookie) {
        throw new Error('Login failed — _boletim_web_session cookie not found');
      }

      this.setSessionCookie(sessionCookie.value);
      logger.info('ConLicitação authentication successful');
    } finally {
      await browser.close();
    }
  }
}
