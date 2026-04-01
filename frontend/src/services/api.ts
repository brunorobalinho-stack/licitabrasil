import type {
  Licitacao, PaginatedResponse, SearchFilters,
  DashboardResumo, EstatisticaPorEstado, EstatisticaPorModalidade,
  Tendencia, FonteDados, Usuario,
} from '../types';

const BASE = '/api/v1';

// ── HTTP helpers ────────────────────────────────────────────────────────

async function request<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> ?? {}),
  };

  const res = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: 'include' });

  if (res.status === 401) {
    const refreshed = await tryRefreshToken();
    if (refreshed) {
      const retry = await fetch(`${BASE}${path}`, { ...opts, headers, credentials: 'include' });
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json();
    }
    throw new ApiError(401, 'Sessão expirada');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({ error: res.statusText }));
    throw new ApiError(res.status, body.error ?? res.statusText);
  }

  return res.json();
}

async function tryRefreshToken(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    });
    return res.ok;
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
    const data = await request<{ user: Usuario }>(
      '/auth/login',
      { method: 'POST', body: JSON.stringify({ email, senha }) },
    );
    return data.user;
  },

  async register(body: { email: string; nome: string; senha: string; empresa?: string; cnpj?: string }) {
    const data = await request<{ user: Usuario }>(
      '/auth/register',
      { method: 'POST', body: JSON.stringify(body) },
    );
    return data.user;
  },

  async me(): Promise<Usuario> {
    return request('/auth/me');
  },

  async logout() {
    await fetch(`${BASE}/auth/logout`, { method: 'POST', credentials: 'include' });
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
  async list(page = 1, pageSize = 20) {
    return request<PaginatedResponse<{ id: string; licitacaoId: string; licitacao: Licitacao; notas: string | null; tags: string[] }>>(
      `/favoritos?page=${page}&pageSize=${pageSize}`,
    );
  },
  async add(licitacaoId: string, notas?: string, tags?: string[]) {
    return request<{ id: string; licitacaoId: string }>(
      '/favoritos',
      { method: 'POST', body: JSON.stringify({ licitacaoId, notas, tags }) },
    );
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
