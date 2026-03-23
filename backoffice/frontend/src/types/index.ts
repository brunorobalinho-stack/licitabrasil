export interface User {
  id: number;
  email: string;
  name: string;
  role: string;
}

export interface DashboardSummary {
  total_clients: number;
  active_contracts: number;
  contracts_expiring_soon: number;
  total_employees: number;
  pending_alerts: number;
  unread_emails: number;
  monthly_revenue: number;
  monthly_expenses: number;
  cash_flow_balance: number;
}

export interface Alert {
  id: number;
  type: string;
  title: string;
  message: string;
  severity: string;
  is_read: boolean;
  reference_id: number | null;
  reference_type: string | null;
  created_at: string;
}

export interface Contract {
  id: number;
  client_id: number;
  title: string;
  description: string | null;
  contract_number: string | null;
  value: number | null;
  start_date: string;
  end_date: string;
  status: 'ativo' | 'vencido' | 'proximo_vencimento' | 'cancelado';
  auto_renew: boolean;
  client_name?: string;
}

export interface EmailRecord {
  id: number;
  client_id: number | null;
  sender: string;
  subject: string;
  body_preview: string | null;
  received_at: string;
  priority: 'alta' | 'media' | 'baixa';
  category: string | null;
  is_read: boolean;
  is_actionable: boolean;
  action_summary: string | null;
  client_name?: string;
}

export interface AgentInfo {
  key: string;
  name: string;
  description: string;
}

export interface AgentRun {
  id: number;
  agent_name: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  result_summary: string | null;
  items_processed: number;
  issues_found: number;
}

export interface CashFlowProjection {
  month: string;
  projected_revenue: number;
  projected_expenses: number;
  balance: number;
}

export interface PayrollAuditIssue {
  employee_name: string;
  employee_cpf: string;
  issue_type: string;
  description: string;
  severity: string;
  reference_month: string;
}

export interface MonthlySummary {
  month: string;
  revenue: number;
  expenses: number;
}

export interface Client {
  id: number;
  name: string;
  cnpj: string;
  email: string | null;
  phone: string | null;
  is_active: boolean;
}
