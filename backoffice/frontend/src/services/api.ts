const BASE_URL = '/api';

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = localStorage.getItem('backoffice_token');
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string> || {}),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('backoffice_token');
    window.location.href = '/login';
    throw new Error('Não autorizado');
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'Erro desconhecido' }));
    throw new Error(err.detail || `Erro ${res.status}`);
  }

  return res.json();
}

export const api = {
  // Auth
  login: (email: string, password: string) =>
    request<{ access_token: string; user: any }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    }),
  me: () => request<any>('/auth/me'),

  // Dashboard
  summary: () => request<any>('/dashboard/summary'),

  // Agents
  listAgents: () => request<any[]>('/agents/available'),
  runAgent: (agent_name: string, params?: Record<string, any>) =>
    request<any>('/agents/run', {
      method: 'POST',
      body: JSON.stringify({ agent_name, params }),
    }),
  agentHistory: (limit = 20) => request<any[]>(`/agents/history?limit=${limit}`),

  // Alerts
  listAlerts: (unreadOnly = false) =>
    request<any[]>(`/alerts/?unread_only=${unreadOnly}`),
  markAlertRead: (id: number) =>
    request<any>(`/alerts/${id}/read`, { method: 'PATCH' }),
  markAllAlertsRead: () =>
    request<any>('/alerts/read-all', { method: 'PATCH' }),

  // Contracts
  listContracts: (status?: string) =>
    request<any[]>(`/contracts/${status ? `?status=${status}` : ''}`),

  // Emails
  listEmails: (params?: { client_id?: number; priority?: string; actionable_only?: boolean }) => {
    const q = new URLSearchParams();
    if (params?.client_id) q.set('client_id', String(params.client_id));
    if (params?.priority) q.set('priority', params.priority);
    if (params?.actionable_only) q.set('actionable_only', 'true');
    return request<any[]>(`/emails/?${q.toString()}`);
  },

  // Transactions
  monthlySummary: (months = 6) =>
    request<any[]>(`/transactions/monthly-summary?months=${months}`),

  // Clients
  listClients: () => request<any[]>('/clients/'),
};
