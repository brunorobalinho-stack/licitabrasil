import { useEffect, useState } from 'react';
import {
  Users, FileText, UserCheck, Bell, Mail,
  TrendingUp, TrendingDown, DollarSign,
} from 'lucide-react';
import { api } from '../services/api';
import { StatCard } from '../components/ui/StatCard';
import { CashFlowChart } from '../components/dashboard/CashFlowChart';
import { AlertsList } from '../components/dashboard/AlertsList';
import { Spinner } from '../components/ui/Spinner';
import type { DashboardSummary } from '../types';

function formatBRL(value: number): string {
  return `R$ ${Number(value).toLocaleString('pt-BR', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

export function DashboardPage() {
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.summary().then(setSummary).finally(() => setLoading(false));
  }, []);

  if (loading || !summary) return <Spinner size="lg" />;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Painel Geral</h2>
        <p className="text-sm text-slate-500 mt-1">Visao consolidada do backoffice</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
        <StatCard title="Clientes Ativos" value={summary.total_clients} icon={Users} color="blue" />
        <StatCard title="Contratos Ativos" value={summary.active_contracts} icon={FileText} color="green" />
        <StatCard
          title="Contratos Vencendo"
          value={summary.contracts_expiring_soon}
          icon={FileText}
          color="amber"
          trend="Proximos 30 dias"
        />
        <StatCard title="Funcionarios" value={summary.total_employees} icon={UserCheck} color="purple" />
        <StatCard title="Alertas Pendentes" value={summary.pending_alerts} icon={Bell} color="red" />
        <StatCard title="E-mails Nao Lidos" value={summary.unread_emails} icon={Mail} color="slate" />
        <StatCard
          title="Receita Mensal"
          value={formatBRL(summary.monthly_revenue)}
          icon={TrendingUp}
          color="green"
        />
        <StatCard
          title="Despesa Mensal"
          value={formatBRL(summary.monthly_expenses)}
          icon={TrendingDown}
          color="red"
        />
      </div>

      {/* Cash Flow Balance */}
      <div className={`rounded-xl p-5 border ${
        summary.cash_flow_balance >= 0
          ? 'bg-emerald-50 border-emerald-200'
          : 'bg-red-50 border-red-200'
      }`}>
        <div className="flex items-center gap-3">
          <DollarSign size={24} className={summary.cash_flow_balance >= 0 ? 'text-emerald-600' : 'text-red-600'} />
          <div>
            <p className="text-sm font-medium text-slate-600">Saldo do Mes</p>
            <p className={`text-3xl font-bold ${
              summary.cash_flow_balance >= 0 ? 'text-emerald-700' : 'text-red-700'
            }`}>
              {formatBRL(summary.cash_flow_balance)}
            </p>
          </div>
        </div>
      </div>

      {/* Charts and Alerts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CashFlowChart />
        <AlertsList limit={8} />
      </div>
    </div>
  );
}
