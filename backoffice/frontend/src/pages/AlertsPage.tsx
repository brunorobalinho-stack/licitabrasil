import { useCallback, useEffect, useState } from 'react';
import { Bell, CheckCheck, Filter } from 'lucide-react';
import { api } from '../services/api';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import type { Alert } from '../types';

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);
  const [unreadOnly, setUnreadOnly] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api.listAlerts(unreadOnly).then(setAlerts).catch(() => setAlerts([])).finally(() => setLoading(false));
  }, [unreadOnly]);

  useEffect(load, [load]);

  const markRead = async (id: number) => {
    await api.markAlertRead(id);
    setAlerts((prev) => prev.map((a) => (a.id === id ? { ...a, is_read: true } : a)));
  };

  const markAllRead = async () => {
    await api.markAllAlertsRead();
    load();
  };

  const TYPE_LABELS: Record<string, string> = {
    salary_payout: 'Folha',
    contract_expiry: 'Contrato',
    payroll_anomaly: 'Auditoria',
    cash_flow_warning: 'Fluxo de Caixa',
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold">Central de Alertas</h2>
          <p className="text-sm text-slate-500 mt-1">
            Todos os alertas gerados pelos agentes
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(e) => setUnreadOnly(e.target.checked)}
              className="rounded"
            />
            Somente nao lidos
          </label>
          <button
            onClick={markAllRead}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-sm text-slate-600 border border-slate-300 hover:bg-slate-50"
          >
            <CheckCheck size={14} /> Marcar todos como lidos
          </button>
        </div>
      </div>

      {loading ? (
        <Spinner />
      ) : alerts.length === 0 ? (
        <div className="text-center py-16">
          <Bell size={48} className="mx-auto text-slate-300 mb-4" />
          <p className="text-slate-400">Nenhum alerta encontrado</p>
        </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => (
            <Card key={alert.id} className={alert.is_read ? 'opacity-60' : ''}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className={`w-2 h-2 rounded-full mt-2 flex-shrink-0 ${
                    alert.severity === 'critical' ? 'bg-red-500' :
                    alert.severity === 'warning' ? 'bg-amber-500' : 'bg-blue-500'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <span className="font-semibold text-sm">{alert.title}</span>
                      <Badge variant={alert.severity}>{alert.severity}</Badge>
                      <Badge variant="default">{TYPE_LABELS[alert.type] || alert.type}</Badge>
                    </div>
                    <p className="text-sm text-slate-600">{alert.message}</p>
                    <p className="text-xs text-slate-400 mt-2">
                      {new Date(alert.created_at).toLocaleString('pt-BR')}
                    </p>
                  </div>
                  {!alert.is_read && (
                    <button
                      onClick={() => markRead(alert.id)}
                      className="text-slate-400 hover:text-blue-600 p-1 flex-shrink-0"
                      title="Marcar como lido"
                    >
                      <CheckCheck size={16} />
                    </button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
