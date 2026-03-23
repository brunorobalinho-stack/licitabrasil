import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { Card, CardHeader, CardContent } from '../components/ui/Card';
import { Badge } from '../components/ui/Badge';
import { Spinner } from '../components/ui/Spinner';
import type { Contract } from '../types';

const STATUS_LABELS: Record<string, string> = {
  ativo: 'Ativo',
  vencido: 'Vencido',
  proximo_vencimento: 'Vencendo',
  cancelado: 'Cancelado',
};

export function ContractsPage() {
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [filter, setFilter] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.listContracts(filter || undefined).then(setContracts).finally(() => setLoading(false));
  }, [filter]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Contratos</h2>
          <p className="text-sm text-slate-500 mt-1">Acompanhamento de vencimento e status</p>
        </div>
        <select
          value={filter}
          onChange={(e) => { setFilter(e.target.value); setLoading(true); }}
          className="px-3 py-2 rounded-lg border border-slate-300 text-sm bg-white"
        >
          <option value="">Todos</option>
          <option value="ativo">Ativos</option>
          <option value="proximo_vencimento">Vencendo</option>
          <option value="vencido">Vencidos</option>
        </select>
      </div>

      {loading ? (
        <Spinner />
      ) : contracts.length === 0 ? (
        <p className="text-slate-400 text-center py-12">Nenhum contrato encontrado</p>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {contracts.map((contract) => (
            <Card key={contract.id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-sm truncate">{contract.title}</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {contract.contract_number} | {contract.client_name}
                    </p>
                  </div>
                  <Badge variant={contract.status}>
                    {STATUS_LABELS[contract.status] || contract.status}
                  </Badge>
                </div>
                <div className="grid grid-cols-3 gap-3 text-xs">
                  <div>
                    <p className="text-slate-400">Inicio</p>
                    <p className="font-medium">
                      {new Date(contract.start_date).toLocaleDateString('pt-BR')}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400">Vencimento</p>
                    <p className="font-medium">
                      {new Date(contract.end_date).toLocaleDateString('pt-BR')}
                    </p>
                  </div>
                  <div>
                    <p className="text-slate-400">Valor</p>
                    <p className="font-medium">
                      {contract.value
                        ? `R$ ${Number(contract.value).toLocaleString('pt-BR')}`
                        : 'N/A'}
                    </p>
                  </div>
                </div>
                {contract.auto_renew && (
                  <p className="text-xs text-blue-600 mt-2">Renovacao automatica</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
