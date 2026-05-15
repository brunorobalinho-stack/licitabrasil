import type {
  Licitacao, PaginatedResponse, SearchFilters,
  DashboardResumo, EstatisticaPorEstado, EstatisticaPorModalidade,
  Tendencia, FonteDados, Usuario,
} from '../types';

const BASE = '/api';

// ── HTTP helpers ────────────────────────────────────────────────────────

function getToken(): string | null {
  return localStorage.getItem('accessToken');
}

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(opts.headers as Record<string, string> ?? {}),
  };

  // credentials: 'include' faz o navegador enviar o cookie httpOnly do
  // refresh token. Ele e path-scoped em /api/auth, entao nas demais rotas
  // nada e enviado -- e inofensivo deixar global.
  const res = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: 'include' });

  if (res.status === 401) {
    // Try refresh (singleton: parallel 401s share one /refresh call)
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers.Authorization = `Bearer ${getToken()}`;
      const retry = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: 'include' });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json();
    }
    // O cookie do refresh token, se ainda existir, ja foi limpo pelo
    // backend no /refresh. So resta limpar o access token local.
    localStorage.removeItem('accessToken');
    window.location.href = '/login';
    throw new ApiError(401, 'Sessão expirada');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText);
  }

  return res.json();
}

// Module-level singleton so concurrent callers share one /refresh round-trip.
// Without this, N parallel 401s caused N parallel /refresh calls; only the
// last token pair survived and the rest of the in-flight requests retried
// with already-rotated tokens.
let refreshingPromise: Promise<boolean> | null = null;

async function tryRefreshToken(): Promise<boolean> {
  if (refreshingPromise) return refreshingPromise;

  const promise = (async (): Promise<boolean> => {
    try {
      // O refresh token vive num cookie httpOnly -- o JS nao o le nem o
      // envia. credentials: 'include' deixa o navegador anexa-lo.
      const res = await fetch(`${BASE}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
      });
      if (!res.ok) {
        // O servidor rejeitou o cookie e ja o limpou na resposta. Logo, o
        // proximo /refresh sai sem cookie e leva 401 na hora -- sem
        // cascata de tentativas com uma credencial que ja se sabe morta.
        // So resta descartar o access token local.
        localStorage.removeItem('accessToken');
        return false;
      }
      const data = await res.json();
      localStorage.setItem('accessToken', data.accessToken);
      return true;
    } catch {
      // Falha de rede: pode ser transiente. Nao mexe em nada -- deixa uma
      // tentativa futura acontecer.
      return false;
    }
  })();

  refreshingPromise = promise;
  // Libera o singleton quando a promise assenta. Se o servidor rejeitou,
  // o token ja foi limpo acima, entao a re-entrada e inofensiva.
  promise.finally(() => {
    refreshingPromise = null;
  });
  return promise;
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// ── Auth ────────────────────────────────────────────────────────────────

export const auth = {
  // O backend devolve so o access token no corpo; o refresh token vem
  // num cookie httpOnly via Set-Cookie, fora do alcance do JS.
  async login(email: string, senha: string) {
    const data = await request<{ user: Usuario; accessToken: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, senha }) },
    );
    localStorage.setItem('accessToken', data.accessToken);
    return data.user;
  },

  async register(body: { email: string; nome: string; senha: string; empresa?: string; cnpj?: string }) {
    const data = await request<{ user: Usuario; accessToken: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify(body) },
    );
    localStorage.setItem('accessToken', data.accessToken);
    return data.user;
  },

  async me(): Promise<Usuario> {
    return request('/auth/me');
  },

  async logout() {
    // Limpa o estado local primeiro (sincrono, antes do await), depois
    // pede ao servidor pra expirar o cookie httpOnly. Best-effort: se a
    // chamada falhar, o cookie expira sozinho.
    localStorage.removeItem('accessToken');
    try {
      await fetch(`${BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
    } catch {
      /* cookie expira sozinho */
    }
  },

  isAuthenticated(): boolean {
    return !!localStorage.getItem('accessToken');
  },
};

// ── Licitações ──────────────────────────────────────────────────────────

export const licitacoes = {
  async list(filters: SearchFilters = {}): Promise<PaginatedResponse<Licitacao>> {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v != null && v !== '') params.set(k, String(v));
    }
    return request(`/licitacoes?${params}`);
  },

  async get(id: string): Promise<Licitacao> {
    return request(`/licitacoes/${id}`);
  },

  async search(q: string, page = 1): Promise<PaginatedResponse<Licitacao>> {
    return request(`/licitacoes/search?q=${encodeURIComponent(q)}&page=${page}`);
  },

  async stats() {
    return request('/licitacoes/stats');
  },

  async timeline(filters: Partial<SearchFilters> = {}): Promise<Licitacao[]> {
    const params = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v != null && v !== '') params.set(k, String(v));
    }
    return request(`/licitacoes/timeline?${params}`);
  },
};

// ── Dashboard ───────────────────────────────────────────────────────────

export const dashboard = {
  async resumo(): Promise<DashboardResumo> {
    return request('/dashboard/resumo');
  },
  async porEstado(): Promise<EstatisticaPorEstado[]> {
    return request('/dashboard/por-estado');
  },
  async porModalidade(): Promise<EstatisticaPorModalidade[]> {
    return request('/dashboard/por-modalidade');
  },
  async tendencias(): Promise<Tendencia[]> {
    return request('/dashboard/tendencias');
  },
};

// ── Fontes ──────────────────────────────────────────────────────────────

export const fontes = {
  async status(): Promise<FonteDados[]> {
    return request('/fontes/status');
  },
  async cobertura() {
    return request('/fontes/cobertura');
  },
};

// ── Favoritos ───────────────────────────────────────────────────────────

export const favoritos = {
  async list(page = 1) {
    return request<PaginatedResponse<{ id: string; licitacao: Licitacao; notas: string | null; tags: string[] }>>(
      `/favoritos?page=${page}`,
    );
  },
  async add(licitacaoId: string, notas?: string, tags?: string[]) {
    return request('/favoritos', {
      method: 'POST',
      body: JSON.stringify({ licitacaoId, notas, tags }),
    });
  },
  async remove(id: string) {
    return request(`/favoritos/${id}`, { method: 'DELETE' });
  },
};

// ── Alertas ─────────────────────────────────────────────────────────────

export const alertas = {
  async list() {
    return request('/alertas');
  },
  async create(body: Record<string, unknown>) {
    return request('/alertas', { method: 'POST', body: JSON.stringify(body) });
  },
  async update(id: string, body: Record<string, unknown>) {
    return request(`/alertas/${id}`, { method: 'PUT', body: JSON.stringify(body) });
  },
  async remove(id: string) {
    return request(`/alertas/${id}`, { method: 'DELETE' });
  },
};
