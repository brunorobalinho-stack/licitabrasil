import { useEffect, useState } from 'react';
import { Mail, AlertTriangle, CheckCircle2 } from 'lucide-react';
import { api } from '../services/api';
import { Card, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import type { EmailRecord } from '../types';

export function EmailsPage() {
  const [emails, setEmails] = useState<EmailRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [priorityFilter, setPriorityFilter] = useState('');
  const [actionableOnly, setActionableOnly] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .listEmails({
        priority: priorityFilter || undefined,
        actionable_only: actionableOnly || undefined,
      })
      .then(setEmails)
      .catch(() => setEmails([]))
      .finally(() => setLoading(false));
  }, [priorityFilter, actionableOnly]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-2xl font-bold">Triagem de E-mails</h2>
          <p className="text-sm text-slate-500 mt-1">E-mails classificados por cliente e prioridade</p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={priorityFilter}
            onChange={(e) => setPriorityFilter(e.target.value)}
            className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
          >
            <option value="">Todas prioridades</option>
            <option value="alta">Alta</option>
            <option value="media">Media</option>
            <option value="baixa">Baixa</option>
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={actionableOnly}
              onChange={(e) => setActionableOnly(e.target.checked)}
              className="rounded"
            />
            Somente acionaveis
          </label>
        </div>
      </div>

      {loading ? (
        <Spinner />
      ) : emails.length === 0 ? (
        <p className="text-slate-400 text-center py-12">Nenhum e-mail encontrado</p>
      ) : (
        <div className="space-y-3">
          {emails.map((email) => (
            <Card key={email.id}>
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <div className={`p-2 rounded-lg ${
                    email.priority === 'alta'
                      ? 'bg-red-50 text-red-500'
                      : email.priority === 'media'
                      ? 'bg-amber-50 text-amber-500'
                      : 'bg-slate-50 text-slate-400'
                  }`}>
                    <Mail size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm">{email.subject}</span>
                      <Badge variant={email.priority}>{email.priority}</Badge>
                      {email.category && <Badge variant="default">{email.category}</Badge>}
                      {email.is_actionable && (
                        <span className="flex items-center gap-1 text-xs text-amber-600">
                          <AlertTriangle size={12} /> Acao necessaria
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-400 mt-1">
                      De: {email.sender}
                      {email.client_name && <> | Cliente: <strong>{email.client_name}</strong></>}
                      {' | '}
                      {new Date(email.received_at).toLocaleString('pt-BR')}
                    </p>
                    {email.body_preview && (
                      <p className="text-sm text-slate-600 mt-2 line-clamp-2">{email.body_preview}</p>
                    )}
                    {email.action_summary && (
                      <p className="text-xs text-amber-700 bg-amber-50 rounded px-2 py-1 mt-2 inline-block">
                        {email.action_summary}
                      </p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
