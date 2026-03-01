import { useEffect, useState } from 'react';
import { dashboard } from '../services/api';
import type { DashboardResumo, EstatisticaPorEstado, EstatisticaPorModalidade, Tendencia } from '../types';
import { MODALIDADE_LABELS, UF_NAMES } from '../types';
import { formatCurrency } from '../lib/utils';
import { BarChart3, TrendingUp, FileText, DollarSign } from 'lucide-react';

export function DashboardPage() {
  const [resumo, setResumo] = useState<DashboardResumo | null>(null);
  const [porEstado, setPorEstado] = useState<EstatisticaPorEstado[]>([]);
  const [porModalidade, setPorModalidade] = useState<EstatisticaPorModalidade[]>([]);
  const [tendencias, setTendencias] = useState<Tendencia[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      dashboard.resumo(),
      dashboard.porEstado(),
      dashboard.porModalidade(),
      dashboard.tendencias(),
    ])
      .then(([r, e, m, t]) => {
        setResumo(r);
        setPorEstado(e);
        setPorModalidade(m);
        setTendencias(t);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl px-4 py-6">
      <h1 className="mb-6 text-2xl font-bold">Dashboard</h1>

      {/* KPI cards */}
      {resumo && (
        <div className="mb-8 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard icon={<FileText />} label="Novas Hoje" value={resumo.novasHoje} color="blue" />
          <KpiCard icon={<BarChart3 />} label="Abertas esta semana" value={resumo.abertasEstaSemana} color="green" />
          <KpiCard icon={<TrendingUp />} label="Encerradas esta semana" value={resumo.encerradasEstaSemana} color="gray" />
          <KpiCard icon={<DollarSign />} label="Volume total (abertas)" value={formatCurrency(resumo.volumeTotalAbertas)} color="emerald" />
        </div>
      )}

      {/* Charts row */}
      <div className="mb-8 grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Top states */}
        <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-4 font-semibold">Licitações por Estado (Top 10)</h2>
          <div className="space-y-2">
            {porEstado.slice(0, 10).map(({ uf, count }) => {
              const max = porEstado[0]?.count ?? 1;
              return (
                <div key={uf} className="flex items-center gap-3">
                  <span className="w-20 text-sm font-medium">{uf} {UF_NAMES[uf] ? `(${UF_NAMES[uf]})` : ''}</span>
                  <div className="flex-1">
                    <div
                      className="h-5 rounded bg-primary/20"
                      style={{ width: `${(count / max) * 100}%` }}
                    >
                      <div
                        className="h-full rounded bg-primary transition-all"
                        style={{ width: '100%' }}
                      />
                    </div>
                  </div>
                  <span className="w-12 text-right text-sm font-semibold">{count}</span>
                </div>
              );
            })}
            {porEstado.length === 0 && <p className="text-sm text-muted-foreground">Sem dados disponíveis</p>}
          </div>
        </div>

        {/* By modalidade */}
        <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
          <h2 className="mb-4 font-semibold">Por Modalidade</h2>
          <div className="space-y-2">
            {porModalidade.slice(0, 10).map(({ modalidade, count }) => {
              const max = porModalidade[0]?.count ?? 1;
              return (
                <div key={modalidade} className="flex items-center gap-3">
                  <span className="w-40 truncate text-sm font-medium">
                    {MODALIDADE_LABELS[modalidade] ?? modalidade}
                  </span>
                  <div className="flex-1">
                    <div
                      className="h-5 rounded bg-green-500/20"
                      style={{ width: `${(count / max) * 100}%` }}
                    >
                      <div className="h-full rounded bg-green-500 transition-all" />
                    </div>
                  </div>
                  <span className="w-12 text-right text-sm font-semibold">{count}</span>
                </div>
              );
            })}
            {porModalidade.length === 0 && <p className="text-sm text-muted-foreground">Sem dados disponíveis</p>}
          </div>
        </div>
      </div>

      {/* Tendências */}
      <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
        <h2 className="mb-4 font-semibold">Publicações nos últimos 30 dias</h2>
        {tendencias.length > 0 ? (
          <div className="flex h-40 items-end gap-1">
            {tendencias.map(({ date, count }) => {
              const max = Math.max(...tendencias.map((t) => t.count), 1);
              const height = (count / max) * 100;
              return (
                <div
                  key={date}
                  className="group relative flex-1"
                  title={`${new Date(date).toLocaleDateString('pt-BR')}: ${count}`}
                >
                  <div
                    className="mx-auto w-full max-w-[12px] rounded-t bg-primary/70 transition-colors group-hover:bg-primary"
                    style={{ height: `${Math.max(height, 2)}%` }}
                  />
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Sem dados disponíveis</p>
        )}
      </div>
    </div>
  );
}

function KpiCard({ icon, label, value, color }: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  color: string;
}) {
  const colorClasses: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600 dark:bg-blue-950 dark:text-blue-400',
    green: 'bg-green-50 text-green-600 dark:bg-green-950 dark:text-green-400',
    gray: 'bg-gray-50 text-gray-600 dark:bg-gray-800 dark:text-gray-400',
    emerald: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-950 dark:text-emerald-400',
  };

  return (
    <div className="rounded-xl border bg-white p-5 dark:border-gray-700 dark:bg-gray-900">
      <div className="flex items-center gap-3">
        <div className={`rounded-lg p-2.5 ${colorClasses[color] ?? colorClasses.blue}`}>
          {icon}
        </div>
        <div>
          <p className="text-2xl font-bold">{typeof value === 'number' ? value.toLocaleString('pt-BR') : value}</p>
          <p className="text-sm text-muted-foreground">{label}</p>
        </div>
      </div>
    </div>
  );
}
