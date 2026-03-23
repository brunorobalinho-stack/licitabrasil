import { AgentPanel } from '../components/agents/AgentPanel';

export function AgentsPage() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Agentes Inteligentes</h2>
        <p className="text-sm text-slate-500 mt-1">
          Execute agentes de auditoria, monitoramento e triagem sob demanda
        </p>
      </div>
      <AgentPanel />
    </div>
  );
}
