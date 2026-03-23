import { useEffect, useState } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { DollarSign, TrendingUp, TrendingDown, Loader2 } from 'lucide-react';
import { api } from '../services/api';
import { Card, CardHeader, CardContent } from '../components/ui/Card';
import { StatCard } from '../components/ui/StatCard';
import { Spinner } from '../components/ui/Spinner';
import { CashFlowChart } from '../components/dashboard/CashFlowChart';
import toast from 'react-hot-toast';

export function CashFlowPage() {
  const [projections, setProjections] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [projecting, setProjecting] = useState(false);

  const runProjection = async () => {
    setProjecting(true);
    try {
      const result = await api.runAgent('cashflow_projection', { months_ahead: 6 });
      setProjections(result.projections || []);
      toast.success('Projecao gerada com sucesso');
    } catch (err: any) {
      toast.error(err.message);
    } finally {
      setProjecting(false);
    }
  };

  const totalProjectedRev = projections.reduce((s, p) => s + Number(p.projected_revenue), 0);
  const totalProjectedExp = projections.reduce((s, p) => s + Number(p.projected_expenses), 0);
  const negativeMonths = projections.filter((p) => Number(p.balance) < 0).length;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Fluxo de Caixa</h2>
          <p className="text-sm text-slate-500 mt-1">Historico e projecoes financeiras</p>
        </div>
        <button
          onClick={runProjection}
          disabled={projecting}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 text-white text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          {projecting ? (
            <>
              <Loader2 size={16} className="animate-spin" />
              Projetando...
            </>
          ) : (
            <>
              <TrendingUp size={16} />
              Gerar Projecao (6 meses)
            </>
          )}
        </button>
      </div>

      {/* Historical Chart */}
      <CashFlowChart />

      {/* Projections */}
      {projections.length > 0 && (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <StatCard
              title="Receita Projetada (6m)"
              value={`R$ ${(totalProjectedRev / 1000).toFixed(0)}k`}
              icon={TrendingUp}
              color="green"
            />
            <StatCard
              title="Despesa Projetada (6m)"
              value={`R$ ${(totalProjectedExp / 1000).toFixed(0)}k`}
              icon={TrendingDown}
              color="red"
            />
            <StatCard
              title="Meses com Deficit"
              value={negativeMonths}
              icon={DollarSign}
              color={negativeMonths > 0 ? 'red' : 'green'}
            />
          </div>

          <Card>
            <CardHeader>
              <h3 className="font-semibold text-lg">Projecao de Fluxo de Caixa</h3>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={350}>
                <AreaChart
                  data={projections.map((p) => ({
                    ...p,
                    projected_revenue: Number(p.projected_revenue),
                    projected_expenses: Number(p.projected_expenses),
                    balance: Number(p.balance),
                  }))}
                  margin={{ top: 10, right: 30, left: 10, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="month" tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 12 }}
                    tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip
                    formatter={(value: number) =>
                      `R$ ${value.toLocaleString('pt-BR', { minimumFractionDigits: 2 })}`
                    }
                  />
                  <Legend />
                  <Area
                    type="monotone" dataKey="projected_revenue" name="Receita"
                    stroke="#059669" fill="#d1fae5" strokeWidth={2}
                  />
                  <Area
                    type="monotone" dataKey="projected_expenses" name="Despesa"
                    stroke="#dc2626" fill="#fee2e2" strokeWidth={2}
                  />
                  <Area
                    type="monotone" dataKey="balance" name="Saldo"
                    stroke="#2563eb" fill="#dbeafe" strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
