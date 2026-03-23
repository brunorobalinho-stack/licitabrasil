import { useEffect, useState } from 'react';
import { Bell, CheckCheck } from 'lucide-react';
import { api } from '../../services/api';
import { Card, CardHeader, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Spinner } from '../ui/Spinner';
import type { Alert } from '../../types';

export function AlertsList({ limit = 10 }: { limit?: number }) {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [loading, setLoading] = useState(true);

  const load = () => {
    setLoading(true);
    api.listAlerts(true).then((data) => {
      setAlerts(data.slice(0, limit));
      setLoading(false);
    });
  };

  useEffect(load, [limit]);

  const markRead = async (id: number) => {
    await api.markAlertRead(id);
    setAlerts((prev) => prev.filter((a) => a.id !== id));
  };

  const markAllRead = async () => {
    await api.markAllAlertsRead();
    setAlerts([]);
  };

  if (loading) return <Spinner />;

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Bell size={18} className="text-amber-500" />
          <h3 className="font-semibold text-lg">Alertas Pendentes</h3>
          {alerts.length > 0 && (
            <Badge variant="critical">{alerts.length}</Badge>
          )}
        </div>
        {alerts.length > 0 && (
          <button
            onClick={markAllRead}
            className="flex items-center gap-1 text-xs text-slate-500 hover:text-slate-700"
          >
            <CheckCheck size={14} /> Marcar todos como lidos
          </button>
        )}
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <p className="text-sm text-slate-400 text-center py-4">Nenhum alerta pendente</p>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-start gap-3 p-3 rounded-lg bg-slate-50 hover:bg-slate-100 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Badge variant={alert.severity}>{alert.severity}</Badge>
                    <span className="text-xs text-slate-400">
                      {new Date(alert.created_at).toLocaleDateString('pt-BR')}
                    </span>
                  </div>
                  <p className="text-sm font-medium">{alert.title}</p>
                  <p className="text-xs text-slate-500 mt-1 line-clamp-2">{alert.message}</p>
                </div>
                <button
                  onClick={() => markRead(alert.id)}
                  className="text-slate-400 hover:text-blue-600 p-1"
                  title="Marcar como lido"
                >
                  <CheckCheck size={16} />
                </button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
