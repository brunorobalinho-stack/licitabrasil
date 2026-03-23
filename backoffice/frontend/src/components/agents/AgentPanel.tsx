import { useEffect, useState } from 'react';
import { Bot, Play, Clock, CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { api } from '../../services/api';
import { Card, CardHeader, CardContent } from '../ui/Card';
import { Badge } from '../ui/Badge';
import { Spinner } from '../ui/Spinner';
import type { AgentInfo, AgentRun } from '../../types';
import toast from 'react-hot-toast';

export function AgentPanel() {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [history, setHistory] = useState<AgentRun[]>([]);
  const [running, setRunning] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.listAgents(), api.agentHistory(10)])
      .then(([a, h]) => {
        setAgents(a);
        setHistory(h);
      })
      .finally(() => setLoading(false));
  }, []);

  const runAgent = async (key: string) => {
    setRunning(key);
    setLastResult(null);
    try {
      const result = await api.runAgent(key);
      setLastResult({ agent: key, ...result });
      toast.success(`Agente "${key}" executado com sucesso`);
      // Refresh history
      const h = await api.agentHistory(10);
      setHistory(h);
    } catch (err: any) {
      toast.error(err.message || 'Erro ao executar agente');
    } finally {
      setRunning(null);
    }
  };

  if (loading) return <Spinner />;

  return (
    <div className="space-y-6">
      {/* Agent Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {agents.map((agent) => (
          <Card key={agent.key}>
            <CardContent className="p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Bot size={20} className="text-blue-600" />
                  <h3 className="font-semibold text-sm">{agent.name}</h3>
                </div>
              </div>
              <p className="text-xs text-slate-500 mb-4">{agent.description}</p>
              <button
                onClick={() => runAgent(agent.key)}
                disabled={running !== null}
                className="w-full flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-sm font-medium
                  bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                {running === agent.key ? (
                  <>
                    <Loader2 size={16} className="animate-spin" />
                    Executando...
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    Executar
                  </>
                )}
              </button>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Last Result */}
      {lastResult && (
        <Card>
          <CardHeader>
            <h3 className="font-semibold">Resultado da Execucao</h3>
          </CardHeader>
          <CardContent>
            <pre className="text-xs bg-slate-50 p-4 rounded-lg overflow-x-auto max-h-96">
              {JSON.stringify(lastResult, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* History */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Clock size={18} className="text-slate-400" />
            <h3 className="font-semibold">Historico de Execucoes</h3>
          </div>
        </CardHeader>
        <CardContent>
          {history.length === 0 ? (
            <p className="text-sm text-slate-400 text-center py-4">Nenhuma execucao registrada</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="text-left py-2 px-3 font-medium text-slate-500">Agente</th>
                    <th className="text-left py-2 px-3 font-medium text-slate-500">Status</th>
                    <th className="text-left py-2 px-3 font-medium text-slate-500">Processados</th>
                    <th className="text-left py-2 px-3 font-medium text-slate-500">Problemas</th>
                    <th className="text-left py-2 px-3 font-medium text-slate-500">Data</th>
                    <th className="text-left py-2 px-3 font-medium text-slate-500">Resumo</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((run) => (
                    <tr key={run.id} className="border-b border-slate-50 hover:bg-slate-50">
                      <td className="py-2 px-3 font-medium">{run.agent_name}</td>
                      <td className="py-2 px-3">
                        <Badge variant={run.status}>{run.status}</Badge>
                      </td>
                      <td className="py-2 px-3">{run.items_processed}</td>
                      <td className="py-2 px-3">
                        {run.issues_found > 0 ? (
                          <span className="text-red-600 font-medium">{run.issues_found}</span>
                        ) : (
                          <span className="text-emerald-600">0</span>
                        )}
                      </td>
                      <td className="py-2 px-3 text-slate-400">
                        {new Date(run.started_at).toLocaleString('pt-BR')}
                      </td>
                      <td className="py-2 px-3 text-xs text-slate-500 max-w-xs truncate">
                        {run.result_summary}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
