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

  const res = await fetch(`${BASE}${path}`, { ...opts, headers });

  if (res.status === 401) {
    // Try refresh
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      headers.Authorization = `Bearer ${getToken()}`;
      const retry = await fetch(`${BASE}${path}`, { ...opts, headers });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json();
    }
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
    window.location.href = '/login';
    throw new ApiError(401, 'Sessão expirada');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText);
  }

  return res.json();
}

async function tryRefreshToken(): Promise<boolean> {
  const refresh = localStorage.getItem('refreshToken');
  if (!refresh) return false;
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refreshToken: refresh }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
    return true;
  } catch {
    return false;
  }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

// ── Auth ────────────────────────────────────────────────────────────────

export const auth = {
  async login(email: string, senha: string) {
    const data = await request<{ user: Usuario; accessToken: string; refreshToken: string }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, senha }) },
    );
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
    return data.user;
  },

  async register(body: { email: string; nome: string; senha: string; empresa?: string; cnpj?: string }) {
    const data = await request<{ user: Usuario; accessToken: string; refreshToken: string }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify(body) },
    );
    localStorage.setItem('accessToken', data.accessToken);
    localStorage.setItem('refreshToken', data.refreshToken);
    return data.user;
  },

  async me(): Promise<Usuario> {
    return request('/auth/me');
  },

  logout() {
    localStorage.removeItem('accessToken');
    localStorage.removeItem('refreshToken');
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
