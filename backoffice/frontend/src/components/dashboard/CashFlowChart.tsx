import { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from 'recharts';
import { api } from '../../services/api';
import { Card, CardHeader, CardContent } from '../ui/Card';
import { Spinner } from '../ui/Spinner';
import type { MonthlySummary } from '../../types';

export function CashFlowChart() {
  const [data, setData] = useState<MonthlySummary[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.monthlySummary(6).then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spinner />;

  const formatted = data.map((d) => ({
    ...d,
    month: d.month.slice(5), // "03" from "2026-03"
    revenue: Number(d.revenue),
    expenses: Number(d.expenses),
  }));

  return (
    <Card>
      <CardHeader>
        <h3 className="font-semibold text-lg">Fluxo de Caixa Mensal</h3>
      </CardHeader>
      <CardContent>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={formatted} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
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
            <Bar dataKey="revenue" name="Receita" fill="#059669" radius={[4, 4, 0, 0]} />
            <Bar dataKey="expenses" name="Despesa" fill="#dc2626" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
